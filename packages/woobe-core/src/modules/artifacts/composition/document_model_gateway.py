"""One governed runtime invocation outside all database transactions."""
import asyncio
import json
from uuid import UUID

from modules.artifacts.application.contracts.document_models import (
    DocumentModelPhase, DocumentModelResponse, DocumentModelUsage,
)
from modules.artifacts.application.services.document_models import SYSTEM_INSTRUCTION, model_input, validate_model_output
from modules.artifacts.domain.models import ArtifactError
from shared.contracts.project_configuration import ConfigurationError
from shared.contracts.llm_cost import calculate_llm_cost
from shared.composition.document_model_operations import operation_configuration_resolver, operation_model_runtime


async def _owned_ack(awaitable):
    task, cancellation = asyncio.create_task(awaitable), None
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError as error:
            if task.cancelled():
                raise
            cancellation = error
    if cancellation is not None:
        raise cancellation
    return result


class GovernedDocumentModelGateway:
    def __init__(self, phases, *, session_factory, encryption_key, runtime=None):
        self._phases = phases
        self._session_factory, self._encryption_key = session_factory, encryption_key
        self._runtime = runtime or operation_model_runtime()

    async def invoke(self, request):
        payload, _ = model_input(request)
        phase = DocumentModelPhase(request)
        receipt = await self._phases['admit_model'](phase)
        binding = request.lease.model_binding
        if receipt['state'] == 'completed':
            return DocumentModelResponse(validate_model_output(json.dumps(receipt['response']), request),
                DocumentModelUsage(input_tokens=receipt['input_tokens'], output_tokens=receipt['output_tokens'],
                    cost_usd=receipt['cost_usd'], cost_status=receipt['cost_status']), binding['fingerprint'])
        dispatched = False
        definition = binding['definition']

        async def verifier(**identity):
            if (str(identity['project_id']), identity['operation_kind'], str(identity['operation_id'])) != (
                request.lease.scope.project_id, 'artifact_processing', request.lease.id):
                raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')
            return await self._phases['model_configuration'](phase)

        resolver = operation_configuration_resolver(verifier=verifier,
            session_factory=self._session_factory, encryption_key=self._encryption_key)

        async def credential(destination):
            nonlocal dispatched
            resolved = await resolver(project_id=UUID(request.lease.scope.project_id),
                operation_kind='artifact_processing', operation_id=UUID(request.lease.id),
                consumer_kind='provider_credential', consumer_id=UUID(definition['credential_id']),
                field_path=binding['configuration']['pins'][0]['field_path'], destination=destination)
            # Once committed, loss of the network outcome is uncertain. A
            # transport re-entry (redirect/retry) cannot send the operation twice.
            await self._phases['dispatch_model'](DocumentModelPhase(request, receipt=receipt))
            dispatched = True
            return resolved.value

        usage, output, error_code, uncertain = DocumentModelUsage(), None, None, False
        try:
            result = await self._runtime.invoke(definition=definition, credential_resolver=credential,
                system_instruction=SYSTEM_INSTRUCTION, input_json=payload,
                max_output_tokens=request.max_output_tokens, timeout_seconds=request.timeout_seconds)
            evidence = result.usage
            if evidence is not None:
                usage = DocumentModelUsage(input_tokens=evidence.metrics.get('input_tokens'),
                    output_tokens=evidence.metrics.get('output_tokens'), cost_usd=evidence.cost_usd,
                    cost_status='reported' if evidence.cost_usd is not None else 'unknown')
            if usage.cost_usd is None:
                estimate = calculate_llm_cost(input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                    pricing_snapshot=definition.get('pricing_snapshot'))
                if estimate['cost_usd'] is not None:
                    usage = DocumentModelUsage(input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                        cost_usd=estimate['cost_usd'], cost_status='estimated')
            texts = [item.value for item in result.outputs if item.modality == 'text']
            if result.tool_calls or len(texts) != 1:
                raise ArtifactError('MODEL_OUTPUT_INVALID', 'Model operation returned an invalid output family')
            output = validate_model_output(texts[0], request)
        except BaseException as error:
            if isinstance(error, ArtifactError) and error.code == 'MODEL_OUTPUT_INVALID':
                error_code = 'MODEL_OUTPUT_INVALID'
            elif dispatched:
                error_code, uncertain = 'EXTERNAL_OPERATION_UNCERTAIN', True
            else:
                error_code = 'MODEL_BINDING_UNAVAILABLE'
            if isinstance(error, asyncio.CancelledError):
                raise
            raise ArtifactError(error_code, 'Governed document model operation could not complete') from None
        finally:
            if dispatched:
                await _owned_ack(self._phases['observe_model'](DocumentModelPhase(request,
                    receipt=receipt, usage=usage, output=output, error_code=error_code, uncertain=uncertain)))
        return DocumentModelResponse(output, usage, binding['fingerprint'])
