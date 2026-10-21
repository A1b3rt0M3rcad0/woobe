"""Short transactions around owned, non-retrying external model operations."""
from datetime import UTC, datetime
import hashlib
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import select

from modules.artifacts.application.contracts.document_models import MAX_JOB_MODEL_TOKENS, MAX_MODEL_CALLS
from modules.artifacts.application.services.document_models import canonical_json
from modules.artifacts.domain.models import ArtifactError
from modules.artifacts.infra.database.jobs import ProcessingJobRepository
from modules.artifacts.infra.database.models import ArtifactProcessingOutboxModel, ProcessingJobModel
from modules.artifacts.infra.database.model_operation_models import ArtifactDocumentModelCallModel as Call


def call_identity(job_id, operation_key):
    return str(uuid5(NAMESPACE_URL, f'woobe:document-model-call:v1:{job_id}:{operation_key}'))


class DocumentModelCallRepository:
    def __init__(self, uow):
        self._uow = uow
        self._jobs = ProcessingJobRepository(uow)

    @staticmethod
    def receipt(row):
        return {'id': row.id, 'nonce': row.nonce, 'state': row.state,
            'response': row.response, 'input_tokens': row.input_tokens,
            'output_tokens': row.output_tokens, 'cost_usd': float(row.cost_usd) if row.cost_usd is not None else None,
            'cost_status': row.cost_status, 'binding_fingerprint': row.binding_fingerprint}

    async def admit(self, lease, *, operation_key, operation, input_fingerprint, input_bytes, max_output_tokens):
        job = await self._jobs.guard(lease)
        binding = job.model_binding
        if binding is None or lease.model_binding != binding:
            raise ArtifactError('MODEL_BINDING_UNAVAILABLE', 'Accepted model binding does not match this operation')
        if (not operation_key or len(operation_key) > 128 or operation not in {'summarize', 'refine_structure'}
            or type(input_bytes) is not int or not 1 <= input_bytes <= 32768
            or type(max_output_tokens) is not int or not 1 <= max_output_tokens <= lease.recipe.limits.max_output_tokens):
            raise ArtifactError('MODEL_BUDGET_EXCEEDED', 'Model operation exceeds its admitted limits')
        rows = (await self._uow.session.execute(select(Call).where(Call.job_id == lease.id)
            .with_for_update().execution_options(populate_existing=True))).scalars().all()
        identity = call_identity(lease.id, operation_key)
        existing = next((row for row in rows if row.id == identity), None)
        if existing is not None:
            if (existing.input_fingerprint, existing.binding_fingerprint, existing.operation, existing.max_output_tokens) != (
                input_fingerprint, binding['fingerprint'], operation, max_output_tokens):
                raise ArtifactError('ARTIFACT_IDEMPOTENCY_CONFLICT', 'Model operation already has a different input')
            if existing.state == 'completed':
                return self.receipt(existing)
            if existing.state != 'admitted':
                raise ArtifactError('EXTERNAL_OPERATION_UNCERTAIN', 'Previously dispatched model operation requires reconciliation')
            # Only a never-dispatched admission may move to a new fenced owner.
            existing.fencing_token, existing.nonce = lease.fencing_token, str(uuid4())
            return self.receipt(existing)
        # UTF-8 bytes are a conservative token reservation, including control
        # payload/schema. Unknown provider usage retains the reservation.
        reserve = input_bytes + max_output_tokens
        if len(rows) >= MAX_MODEL_CALLS or sum(row.budget_tokens for row in rows) + reserve > MAX_JOB_MODEL_TOKENS:
            raise ArtifactError('MODEL_BUDGET_EXCEEDED', 'Aggregate job model budget is exhausted')
        row = Call(id=identity, project_id=UUID(lease.scope.project_id), environment=lease.scope.environment.value,
            workspace_id=lease.workspace_id, job_id=lease.id, operation_key=operation_key, operation=operation,
            input_fingerprint=input_fingerprint, binding_fingerprint=binding['fingerprint'],
            fencing_token=lease.fencing_token, nonce=str(uuid4()), state='admitted', budget_tokens=reserve,
            max_output_tokens=max_output_tokens, cost_status='unknown', observation_revision=0)
        self._uow.session.add(row)
        await self._uow.session.flush()
        return self.receipt(row)

    async def dispatched(self, lease, call_id, nonce):
        await self._jobs.guard(lease)
        row = await self._owned(lease, call_id, nonce)
        if row.state != 'admitted':
            raise ArtifactError('EXTERNAL_OPERATION_UNCERTAIN', 'Model operation cannot be dispatched again')
        row.state, row.started_at = 'in_flight', datetime.now(UTC)

    async def _owned(self, lease, call_id, nonce):
        row = (await self._uow.session.execute(select(Call).where(Call.id == call_id,
            Call.job_id == lease.id, Call.project_id == UUID(lease.scope.project_id),
            Call.environment == lease.scope.environment.value, Call.workspace_id == lease.workspace_id)
            .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
        if row is None or row.nonce != nonce or row.fencing_token != lease.fencing_token:
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Model operation acknowledgement is not owned')
        return row

    async def observed(self, lease, *, call_id, nonce, usage, output=None, error_code=None, uncertain=False):
        # Acknowledgement of previously admitted I/O survives lease/revocation;
        # it cannot authorize dispatch or publish any document generation.
        row = await self._owned(lease, call_id, nonce)
        if row.state == 'completed':
            return self.receipt(row)
        if row.state not in {'in_flight', 'uncertain'}:
            raise ArtifactError('ARTIFACT_IDEMPOTENCY_CONFLICT', 'Model operation has not been dispatched')
        encoded = canonical_json(output.model_dump(mode='json')) if output is not None else None
        if encoded is not None and len(encoded) > 65536:
            raise ArtifactError('MODEL_OUTPUT_INVALID', 'Model checkpoint exceeds its bounded result contract')
        row.input_tokens, row.output_tokens = usage.input_tokens, usage.output_tokens
        row.cost_usd, row.cost_status = usage.cost_usd, usage.cost_status
        row.provider_request_id = usage.provider_request_id[:255] if usage.provider_request_id else None
        row.error_code, row.finished_at = error_code, datetime.now(UTC)
        row.observation_revision += 1
        if encoded is not None:
            row.state, row.response = 'completed', output.model_dump(mode='json')
            row.response_sha256 = hashlib.sha256(encoded).hexdigest()
        else:
            row.state = 'uncertain' if uncertain else 'failed'
        job = await self._uow.session.get(ProcessingJobModel, lease.id)
        definition = job.model_binding.get('definition')
        if definition is not None:
            event_id = uuid5(NAMESPACE_URL, f'woobe:document-model-usage-observation:v1:{row.id}:{row.observation_revision}')
            payload = {'schema_version': '1', 'usage_event_id': str(uuid5(NAMESPACE_URL, 'woobe:document-model-usage:v1:' + row.id)),
                'project_id': str(row.project_id), 'environment': row.environment,
                'job_id': row.job_id, 'call_id': row.id, 'provider': definition['provider'], 'model': definition['model'],
                'provider_model_id': definition['model_id'], 'occurred_at': row.started_at.isoformat(),
                'observation_revision': row.observation_revision, 'input_tokens': row.input_tokens,
                'output_tokens': row.output_tokens, 'cost_usd': float(row.cost_usd) if row.cost_usd is not None else None,
                'cost_status': row.cost_status, 'pricing_snapshot': definition.get('pricing_snapshot')}
            self._uow.session.add(ArtifactProcessingOutboxModel(id=event_id, aggregate_type='artifact-document-model-call',
                aggregate_id=UUID(row.id), event_type='artifact.processing.model_usage.v1', event_version=1,
                routing_key='artifact.processing.model_usage.v1', payload=payload,
                idempotency_key='artifact-model-usage:' + str(event_id), status='pending', attempts=0))
        await self._uow.session.flush()
        return self.receipt(row)
