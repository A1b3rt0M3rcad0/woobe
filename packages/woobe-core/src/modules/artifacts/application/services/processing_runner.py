import asyncio
from contextlib import suppress

from modules.artifacts.application.contracts.jobs import (
    ClaimProcessingJob, ProcessingCancellationRequested, ProcessingJobResult,
    ProcessingLeaseLost, WorkerPhase,
)
from modules.artifacts.application.ports.processing import ProcessingExecution, ProcessingPipeline
from modules.artifacts.domain.models import ArtifactError
from shared.contracts.object_storage import ObjectStorageError


class ProcessingRunner:
    """One claimed job per existing Worker poll, with independent short phases."""

    def __init__(self, deliver, claim, prepare, heartbeat, checkpoint, finish, storage,
                 *, pipeline: ProcessingPipeline | None = None, lease_seconds=30, project_limit=4, workspace_limit=2, publication_phase=None):
        self._deliver, self._claim, self._prepare = deliver, claim, prepare
        self._heartbeat, self._checkpoint, self._finish = heartbeat, checkpoint, finish
        self._storage, self._pipeline = storage, pipeline
        self._publication_phase = publication_phase
        self._lease_seconds = lease_seconds
        self._project_limit, self._workspace_limit = project_limit, workspace_limit

    async def _execute(self, lease):
        prepared = await self._prepare(WorkerPhase(lease))
        source = prepared['source']
        store = self._storage(prepared['storage_profile'])
        checkpoints = dict(lease.checkpoints)

        async def checkpoint(stage, value):
            # A durable checkpoint is acknowledged only after current authority
            # and fencing are checked in a new transaction.
            await self._checkpoint(WorkerPhase(lease, stage=stage, checkpoint=value))
            checkpoints[stage] = value

        async def reauthorize():
            return await self._prepare(WorkerPhase(lease))

        if 'verify_original' not in checkpoints:
            actual = await store.stat(source.object_key)
            if ((actual.size_bytes, actual.sha256, actual.content_type) != (
                source.size_bytes, source.sha256, source.content_type)
                or (source.storage_version_id is not None and actual.version_id != source.storage_version_id)):
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Processing original failed integrity verification')
            await checkpoint('verify_original', {'sha256': actual.sha256,
                'size_bytes': actual.size_bytes, 'version_id': actual.version_id})
        publication = None
        if lease.recipe.mode == 'store_only':
            result = ProcessingJobResult(mode='store_only', processing_performed=False, source_sha256=source.sha256)
        elif self._pipeline is None:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Pinned processing implementation is unavailable')
        else:
            context = ProcessingExecution(lease, source, store, checkpoints, reauthorize, self._publication_phase)
            initialize = getattr(self._pipeline, 'initialize', None)
            if initialize is not None:
                await initialize(context)
            stages = self._pipeline.stages(lease.recipe)
            if len(stages) > 63 or len({stage.name for stage in stages}) != len(stages):
                raise ValueError('Processing pipeline stages must be unique and bounded')
            for stage in stages:
                if stage.name == 'verify_original':
                    raise ValueError('Original verification is owned by the coordinator')
                await reauthorize()
                if stage.name not in checkpoints:
                    await checkpoint(stage.name, await stage.execute(context))
            result = ProcessingJobResult.model_validate(self._pipeline.result(context))
            publication = context.transient.get('publication')
        await self._finish(WorkerPhase(lease, status='succeeded', result=result.model_dump(mode='json'), publication=publication))

    async def _keep_alive(self, lease, operation):
        while True:
            await asyncio.sleep(max(0.1, lease.lease_seconds / 3))
            try:
                current = await self._heartbeat(WorkerPhase(lease))
            except Exception:
                current = False
            if not current:
                operation.cancel()
                return

    async def run_once(self, worker_id):
        await self._deliver(50)
        lease = await self._claim(ClaimProcessingJob(worker_id, self._lease_seconds,
                                                     self._project_limit, self._workspace_limit))
        if lease is None:
            return None
        operation = asyncio.create_task(self._execute(lease))
        heartbeat = asyncio.create_task(self._keep_alive(lease, operation))
        try:
            async with asyncio.timeout(lease.recipe.limits.timeout_seconds):
                await operation
        except ProcessingLeaseLost:
            # A newer owner controls all publication. Do not write stale state.
            pass
        except ProcessingCancellationRequested:
            await self._finish(WorkerPhase(lease, status='cancelled'))
        except asyncio.CancelledError:
            # Heartbeat/caller cancellation first awaits owned resource cleanup.
            operation.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await operation
            # A requested cancellation is confirmed; otherwise the interrupted
            # attempt is retried with its already durable checkpoints.
            await asyncio.shield(self._finish(WorkerPhase(lease, status='failed',
                error_code='PROCESSING_INTERRUPTED', retryable=True)))
            if asyncio.current_task().cancelling():
                raise
        except TimeoutError:
            await self._finish(WorkerPhase(lease, status='failed', error_code='PROCESSING_TIMEOUT', retryable=True))
        except ArtifactError as error:
            await self._finish(WorkerPhase(lease,
                status='uncertain' if error.code == 'EXTERNAL_OPERATION_UNCERTAIN' else 'failed',
                error_code=str(error.code), retryable=error.retryable))
        except ObjectStorageError as error:
            await self._finish(WorkerPhase(lease, status='failed',
                error_code='UPLOAD_INTEGRITY_MISMATCH' if error.code == 'integrity' else 'ARTIFACT_STORAGE_UNAVAILABLE',
                retryable=error.code == 'unavailable'))
        except Exception:
            await self._finish(WorkerPhase(lease, status='failed', error_code='PROCESSING_INTERNAL_ERROR', retryable=True))
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
        return lease.id
