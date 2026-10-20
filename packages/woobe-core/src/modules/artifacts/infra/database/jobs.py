from datetime import UTC, datetime, timedelta
import hashlib
import json
import re
from uuid import UUID, uuid4

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased

from modules.artifacts.application.authorization import principal_identity
from modules.artifacts.application.contracts.api import ArtifactReference
from modules.artifacts.application.contracts.jobs import (
    JobLease, ProcessingCancellationRequested, ProcessingJobView, ProcessingLeaseLost,
)
from modules.artifacts.application.contracts.processing import ProcessingRecipe
from modules.artifacts.application.principal_snapshot import freeze_principal, restore_principal
from modules.artifacts.application.processing_registry import processing_fingerprint
from modules.artifacts.domain.models import ArtifactError, Scope
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.models import (
    ArtifactProcessingInboxModel, ArtifactProcessingOutboxModel, ProcessingAttemptModel, ProcessingJobModel,
    ProcessingProjectQueueModel, ProcessingWorkspaceQueueModel,
)
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork


TERMINAL = {'succeeded', 'failed', 'cancelled', 'uncertain'}
EVENT = 'artifact.processing.requested.v1'


def job_view(row):
    return ProcessingJobView(id=row.id, workspace_id=row.workspace_id, operation_id=row.operation_id,
        source=ArtifactReference(artifact_id=row.artifact_id, revision_id=row.revision_id),
        profile_id=row.profile_id, profile_revision=row.profile_revision, recipe_fingerprint=row.recipe_fingerprint,
        status=row.status, attempt=row.attempt, completed_stages=tuple(sorted(row.checkpoints)),
        result=row.result, error_code=row.error_code, retryable=row.retryable)


def request_fingerprint(request):
    payload = {'artifact_id': request.artifact_id, 'definition': request.definition.model_dump(mode='json')}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class ProcessingJobRepository:
    def __init__(self, uow: ArtifactsUnitOfWork, *, project_max_jobs=1000, workspace_max_jobs=100):
        self._project_max_jobs, self._workspace_max_jobs = project_max_jobs, workspace_max_jobs
        self._uow = uow
        self._catalog = CatalogRepository(uow)

    async def _now(self):
        # Lease decisions use one authoritative database clock across replicas.
        return await self._uow.session.scalar(select(func.clock_timestamp()))

    async def lookup(self, request, subject):
        row = (await self._uow.session.execute(select(ProcessingJobModel).where(
            ProcessingJobModel.project_id == UUID(request.scope.project_id),
            ProcessingJobModel.environment == request.scope.environment.value,
            ProcessingJobModel.workspace_id == request.workspace_id,
            ProcessingJobModel.operation_id == request.definition.operation_id,
        ))).scalar_one_or_none()
        if row is None:
            return None
        if row.principal_id != subject:
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Processing operation access is denied')
        if row.request_fingerprint != request_fingerprint(request):
            raise ArtifactError('ARTIFACT_IDEMPOTENCY_CONFLICT', 'Processing operation has a different request')
        return job_view(row)

    async def request(self, request, source, recipe, profile_id, profile_revision):
        workspace = await self._catalog.workspace_row(request.scope, request.workspace_id, lock=True)
        if workspace.status != 'active':
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Workspace does not accept processing')
        await self._catalog.artifact_row(request.scope, workspace.id, request.artifact_id)
        replay = await self.lookup(request, principal_identity(request.principal))
        if replay is not None:
            return replay
        await self._uow.session.execute(select(func.pg_advisory_xact_lock(
            func.hashtextextended('artifact-processing-project:' + request.scope.project_id, 0))))
        pending = (await self._uow.session.execute(select(func.count(),
            func.count().filter(ProcessingJobModel.workspace_id == workspace.id),
        ).where(ProcessingJobModel.project_id == UUID(request.scope.project_id),
                ProcessingJobModel.status.in_(['queued', 'running', 'cancel_requested'])))).one()
        if pending[0] >= self._project_max_jobs or pending[1] >= self._workspace_max_jobs:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Processing queue admission limit exceeded', retryable=True)
        await self._uow.session.execute(insert(ProcessingProjectQueueModel).values(
            project_id=UUID(request.scope.project_id)).on_conflict_do_nothing())
        await self._uow.session.execute(insert(ProcessingWorkspaceQueueModel).values(
            workspace_id=workspace.id).on_conflict_do_nothing())
        row = ProcessingJobModel(id=str(uuid4()), project_id=UUID(request.scope.project_id),
            environment=request.scope.environment.value, workspace_id=workspace.id,
            artifact_id=request.artifact_id, revision_id=source.id,
            principal_id=principal_identity(request.principal), principal_snapshot=freeze_principal(request.principal),
            operation_id=request.definition.operation_id, request_fingerprint=request_fingerprint(request),
            processing_fingerprint=processing_fingerprint(sha256=source.sha256, size_bytes=source.size_bytes,
                content_type=source.content_type, recipe=recipe), profile_id=profile_id, profile_revision=profile_revision,
            recipe=recipe.model_dump(mode='json'), recipe_fingerprint=recipe.fingerprint(),
            status='queued', attempt=0, max_attempts=3, fencing_token=0, checkpoints={}, retryable=False)
        self._uow.session.add(row)
        self._uow.session.add(ArtifactProcessingOutboxModel(id=uuid4(), aggregate_type='artifact-processing-job',
            aggregate_id=UUID(row.id), event_type=EVENT, event_version=1, routing_key=EVENT,
            payload={'job_id': row.id}, idempotency_key=EVENT + ':' + row.id, status='pending', attempts=0))
        await self._uow.session.flush()
        return job_view(row)

    async def _owned(self, request, subject, *, lock=False):
        query = select(ProcessingJobModel).where(
            ProcessingJobModel.id == request.job_id, ProcessingJobModel.workspace_id == request.workspace_id,
            ProcessingJobModel.project_id == UUID(request.scope.project_id),
            ProcessingJobModel.environment == request.scope.environment.value,
            ProcessingJobModel.principal_id == subject,
        )
        if request.artifact_id is not None:
            query = query.where(ProcessingJobModel.artifact_id == request.artifact_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = (await self._uow.session.execute(query)).scalar_one_or_none()
        if row is None:
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Processing job access is denied')
        return row

    async def read(self, request, subject):
        return job_view(await self._owned(request, subject))

    async def cancel(self, request, subject):
        row = await self._owned(request, subject, lock=True)
        if row.status in TERMINAL:
            return job_view(row)
        now = await self._now()
        row.cancel_requested_at = now
        if row.status == 'queued':
            row.status = 'cancelled'
        elif row.lease_until is not None and row.lease_until <= now:
            row.status = 'uncertain'
            row.error_code = 'EXTERNAL_OPERATION_UNCERTAIN'
        else:
            row.status = 'cancel_requested'
        return job_view(row)

    async def deliver(self, limit):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Processing delivery limit must be between 1 and 100')
        rows = (await self._uow.session.execute(select(ArtifactProcessingOutboxModel).where(
            ArtifactProcessingOutboxModel.status == 'pending',
            ArtifactProcessingOutboxModel.available_at <= datetime.now(UTC),
        ).order_by(ArtifactProcessingOutboxModel.created_at, ArtifactProcessingOutboxModel.id)
          .limit(limit).with_for_update(skip_locked=True))).scalars()
        count = 0
        for row in rows:
            # Local durable delivery uses the same outbox/inbox schema as the
            # existing workers. It remains available with RabbitMQ disabled.
            await self._uow.session.execute(insert(ArtifactProcessingInboxModel).values(
                id=uuid4(), message_id=str(row.id), producer_module='artifacts', consumer_module='artifacts',
                outbox_origin_id=row.id, aggregate_type=row.aggregate_type, event_type=row.event_type,
                event_version=row.event_version, routing_key=row.routing_key, payload=row.payload,
                idempotency_key=row.idempotency_key, status='processed', attempts=1,
                processed_at=datetime.now(UTC), consumer_name='artifact-processing-queue',
            ).on_conflict_do_nothing())
            row.status = 'published'
            row.published_at = datetime.now(UTC)
            row.attempts += 1
            count += 1
        return count

    async def claim(self, request):
        if (not 3 <= request.lease_seconds <= 300 or not 1 <= request.project_limit <= 64
                or not 1 <= request.workspace_limit <= request.project_limit or not request.worker_id
                or len(request.worker_id) > 128):
            raise ValueError('Invalid processing lease or concurrency budget')
        now = await self._now()
        # No cancellation ACK was observed before the owner's lease expired.
        # Preserve uncertainty instead of promising that its I/O stopped.
        expired_cancel = select(ProcessingJobModel.id).where(
            ProcessingJobModel.status == 'cancel_requested', ProcessingJobModel.lease_until <= now,
        ).limit(100).with_for_update(skip_locked=True)
        await self._uow.session.execute(update(ProcessingJobModel).where(
            ProcessingJobModel.id.in_(expired_cancel),
        ).values(status='uncertain', error_code='EXTERNAL_OPERATION_UNCERTAIN'))
        running = aliased(ProcessingJobModel)
        live = and_(running.status.in_(['running', 'cancel_requested']), running.lease_until > now)
        project_count = select(func.count()).select_from(running).where(live,
            running.project_id == ProcessingJobModel.project_id).correlate(ProcessingJobModel).scalar_subquery()
        workspace_count = select(func.count()).select_from(running).where(live,
            running.workspace_id == ProcessingJobModel.workspace_id).correlate(ProcessingJobModel).scalar_subquery()
        delivered = exists(select(ArtifactProcessingInboxModel.id).where(
            ArtifactProcessingInboxModel.payload['job_id'].astext == ProcessingJobModel.id,
            ArtifactProcessingInboxModel.status == 'processed'))
        query = select(ProcessingJobModel).join(ProcessingProjectQueueModel,
            ProcessingProjectQueueModel.project_id == ProcessingJobModel.project_id).join(
            ProcessingWorkspaceQueueModel, ProcessingWorkspaceQueueModel.workspace_id == ProcessingJobModel.workspace_id).where(delivered,
            or_(and_(ProcessingJobModel.status == 'queued', ProcessingJobModel.available_at <= now),
                and_(ProcessingJobModel.status == 'running', ProcessingJobModel.lease_until <= now)),
            project_count < request.project_limit, workspace_count < request.workspace_limit,
        ).order_by(ProcessingProjectQueueModel.last_claim_at.asc().nulls_first(),
            ProcessingWorkspaceQueueModel.last_claim_at.asc().nulls_first(),
            ProcessingJobModel.created_at, ProcessingJobModel.id).limit(50).with_for_update(
                skip_locked=True, of=ProcessingJobModel)
        candidates = list((await self._uow.session.execute(query)).scalars())
        for row in candidates:
            locked = await self._uow.session.scalar(select(func.pg_try_advisory_xact_lock(
                func.hashtextextended('artifact-processing-project:' + str(row.project_id), 0))))
            if not locked:
                continue
            counts = (await self._uow.session.execute(select(
                func.count(), func.count().filter(ProcessingJobModel.workspace_id == row.workspace_id),
            ).where(ProcessingJobModel.project_id == row.project_id,
                ProcessingJobModel.status.in_(['running', 'cancel_requested']), ProcessingJobModel.lease_until > now))).one()
            if counts[0] >= request.project_limit or counts[1] >= request.workspace_limit:
                continue
            if row.attempt:
                await self._uow.session.execute(update(ProcessingAttemptModel).where(
                    ProcessingAttemptModel.job_id == row.id, ProcessingAttemptModel.status == 'running',
                ).values(status='expired', finished_at=now, error_code='PROCESSING_LEASE_EXPIRED'))
            if row.attempt >= row.max_attempts:
                row.status, row.retryable, row.error_code = 'failed', False, 'PROCESSING_ATTEMPTS_EXHAUSTED'
                row.lease_until, row.worker_id = None, None
                continue
            try:
                actor = restore_principal(row.principal_snapshot)
                recipe = ProcessingRecipe.model_validate(row.recipe)
            except (KeyError, ValueError, TypeError):
                row.status, row.retryable, row.error_code = 'failed', False, 'INVALID_PROCESSING_SNAPSHOT'
                row.lease_until, row.worker_id = None, None
                continue
            await self._uow.session.execute(update(ProcessingProjectQueueModel).where(
                ProcessingProjectQueueModel.project_id == row.project_id).values(last_claim_at=now))
            await self._uow.session.execute(update(ProcessingWorkspaceQueueModel).where(
                ProcessingWorkspaceQueueModel.workspace_id == row.workspace_id).values(last_claim_at=now))
            row.status, row.worker_id = 'running', request.worker_id
            row.attempt += 1
            row.fencing_token += 1
            row.lease_until = now + timedelta(seconds=request.lease_seconds)
            row.error_code, row.retryable = None, False
            attempt = ProcessingAttemptModel(id=str(uuid4()), job_id=row.id, fencing_token=row.fencing_token,
                worker_id=request.worker_id, status='running')
            self._uow.session.add(attempt)
            await self._uow.session.flush()
            return JobLease(row.id, attempt.id, request.worker_id, Scope(str(row.project_id), row.environment),
                row.workspace_id, actor, row.fencing_token,
                row.lease_until, request.lease_seconds, recipe,
                ArtifactReference(artifact_id=row.artifact_id, revision_id=row.revision_id),
                row.profile_id, row.profile_revision, dict(row.checkpoints))
        return None

    async def _lease_row(self, lease):
        row = (await self._uow.session.execute(select(ProcessingJobModel).where(
            ProcessingJobModel.id == lease.id, ProcessingJobModel.workspace_id == lease.workspace_id,
            ProcessingJobModel.project_id == UUID(lease.scope.project_id),
            ProcessingJobModel.environment == lease.scope.environment.value,
        ).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
        attempt = await self._uow.session.get(ProcessingAttemptModel, lease.attempt_id)
        if (row is None or attempt is None or row.fencing_token != lease.fencing_token
                or (row.worker_id != lease.worker_id and row.status not in {'succeeded', 'failed', 'cancelled'})
                or attempt.job_id != row.id
                or attempt.fencing_token != lease.fencing_token or attempt.worker_id != lease.worker_id):
            raise ProcessingLeaseLost('Processing lease is no longer current')
        return row, attempt

    async def guard(self, lease):
        row, attempt = await self._lease_row(lease)
        if row.status in {'cancel_requested', 'uncertain'}:
            raise ProcessingCancellationRequested('Cancellation requires worker reconciliation')
        if row.status != 'running' or row.lease_until <= await self._now():
            raise ProcessingLeaseLost('Processing lease expired')
        return row

    async def heartbeat(self, phase):
        try:
            row = await self.guard(phase.lease)
        except (ProcessingLeaseLost, ProcessingCancellationRequested):
            return False
        duration = phase.lease.lease_seconds
        if type(duration) is not int or not 3 <= duration <= 300:
            raise ValueError('Invalid processing heartbeat lease duration')
        row.lease_until = await self._now() + timedelta(seconds=duration)
        return True

    async def checkpoint(self, phase):
        row = await self.guard(phase.lease)
        if (re.fullmatch(r'[a-z][a-z0-9_]{0,63}', phase.stage) is None
                or not isinstance(phase.checkpoint, dict)):
            raise ValueError('Processing checkpoints require bounded stage identity and metadata')
        if len(json.dumps(phase.checkpoint).encode()) > 65_536:
            raise ValueError('Processing checkpoint metadata exceeds 64 KiB')
        if phase.stage in row.checkpoints:
            if row.checkpoints[phase.stage] != phase.checkpoint:
                raise ArtifactError('ARTIFACT_IDEMPOTENCY_CONFLICT', 'Durable processing checkpoint already differs')
        else:
            updated = {**row.checkpoints, phase.stage: phase.checkpoint}
            if len(updated) > 64 or len(json.dumps(updated).encode()) > 262_144:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Processing checkpoint manifest exceeds its metadata limit')
            row.checkpoints = updated
        return job_view(row)

    async def terminal_ack(self, phase):
        try:
            row, attempt = await self._lease_row(phase.lease)
        except ProcessingLeaseLost:
            return False
        if row.status in {'succeeded', 'failed', 'cancelled'}:
            return row.status == phase.status and (row.status != 'succeeded' or row.result == phase.result)
        return None

    async def finish(self, phase):
        try:
            row, attempt = await self._lease_row(phase.lease)
        except ProcessingLeaseLost:
            return False
        if row.status in {'succeeded', 'failed', 'cancelled'}:
            return row.status == phase.status
        if phase.status == 'succeeded':
            await self.guard(phase.lease)
            row.status, row.result, row.retryable = 'succeeded', phase.result, False
        elif row.status in {'cancel_requested', 'uncertain'} or phase.status == 'cancelled':
            row.status, row.result, row.retryable = 'cancelled', None, False
        elif phase.status == 'failed':
            row.retryable = phase.retryable and row.attempt < row.max_attempts
            row.status = 'queued' if row.retryable else 'failed'
            row.available_at = await self._now() + timedelta(seconds=min(30, 2 ** row.attempt))
        else:
            raise ValueError('Unsupported processing terminal state')
        row.error_code = phase.error_code
        row.lease_until = None
        row.worker_id = None
        attempt.status = 'failed' if row.status == 'queued' else row.status
        attempt.finished_at = await self._now()
        attempt.error_code = phase.error_code
        return True
