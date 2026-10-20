import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from modules.artifacts.application.authorization import ArtifactAuthorization
from modules.artifacts.application.contracts.jobs import (
    ClaimProcessingJob, ProcessingJobResult, ProcessingLeaseLost, ProcessingRequest,
    ReadProcessingJob, RequestProcessing, WorkerPhase,
)
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.application.processing_registry import ProcessingRegistry
from modules.artifacts.application.use_cases.jobs import ProcessingJobUseCases
from modules.artifacts.application.use_cases.profiles import ProfileUseCases
from modules.artifacts.domain.models import ArtifactError
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.jobs import ProcessingJobRepository
from modules.artifacts.infra.database.models import (
    ArtifactProcessingInboxModel, ArtifactProcessingOutboxModel, ProcessingJobModel,
)
from modules.artifacts.infra.database.profiles import ProfileRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from tests.integration.artifacts.test_files_postgres import prepare
from tests.integration.artifacts.test_uploads_postgres import object_store as object_store


async def execute(engine, method, request, *, project_max_jobs=1000, workspace_max_jobs=100, registry=None):
    async with ArtifactsUnitOfWork(engine) as uow:
        grants = GrantRepository(uow)
        authorization = ArtifactAuthorization(ExistingPrincipalAuthority(uow), grants)
        registry = registry or ProcessingRegistry()
        profiles = ProfileUseCases(ProfileRepository(uow), authorization, registry, CursorCodec(b'f' * 32))
        jobs = ProcessingJobUseCases(ProcessingJobRepository(uow, project_max_jobs=project_max_jobs, workspace_max_jobs=workspace_max_jobs), CatalogRepository(uow), profiles, authorization, registry)
        return await getattr(jobs, method)(request)


async def setup(engine, project, store):
    files, text_request = await prepare(engine, project, store)
    published = await files.write_text(text_request)
    return files, RequestProcessing(text_request.principal, text_request.scope, text_request.workspace_id,
        published.receipt.artifact_id, ProcessingRequest(operation_id=uuid4().hex, revision_id=published.receipt.revision_id))


def read_request(request, job):
    return ReadProcessingJob(request.principal, request.scope, request.workspace_id, job.id)


async def test_request_and_outbox_are_atomic_idempotent_and_delivery_is_deduplicated(engine, artifacts_database, object_store):
    files, request = await setup(engine, artifacts_database['project_id'], object_store)
    first, replay = await asyncio.gather(execute(engine, 'request', request), execute(engine, 'request', request))
    assert first.id == replay.id and first.status == 'queued'
    with pytest.raises(ArtifactError) as failure:
        await execute(engine, 'request', replace(request, definition=request.definition.model_copy(update={'revision_id': 'different'})))
    assert failure.value.code == 'ARTIFACT_IDEMPOTENCY_CONFLICT'
    assert await execute(engine, 'claim', ClaimProcessingJob('before-delivery')) is None
    assert await execute(engine, 'deliver', 50) == 1
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text("UPDATE artifacts.processing_outbox SET status='pending' WHERE aggregate_id=:job"), {'job': first.id})
    assert await execute(engine, 'deliver', 50) == 1
    async with ArtifactsUnitOfWork(engine) as uow:
        assert await uow.session.scalar(select(func.count()).select_from(ArtifactProcessingInboxModel).where(ArtifactProcessingInboxModel.payload['job_id'].astext == first.id)) == 1
        assert await uow.session.scalar(select(func.count()).select_from(ArtifactProcessingOutboxModel).where(ArtifactProcessingOutboxModel.payload['job_id'].astext == first.id)) == 1
    lease = await execute(engine, 'claim', ClaimProcessingJob('current-owner'))
    assert lease.id == first.id and lease.fencing_token == 1
    prepared = await execute(engine, 'prepare', WorkerPhase(lease))
    metadata = await object_store.stat(prepared['source'].object_key)
    await execute(engine, 'checkpoint', WorkerPhase(lease, stage='verify_original', checkpoint={'sha256': metadata.sha256}))
    result = ProcessingJobResult(mode='store_only', processing_performed=False, source_sha256=metadata.sha256).model_dump(mode='json')
    assert await execute(engine, 'finish', WorkerPhase(lease, status='succeeded', result=result))
    assert await execute(engine, 'finish', WorkerPhase(lease, status='succeeded', result=result))
    complete = await execute(engine, 'read', read_request(request, first))
    assert complete.status == 'succeeded' and complete.result.source_sha256 == metadata.sha256
    assert complete.completed_stages == ('verify_original',)
    assert (await execute(engine, 'request', request)).id == first.id


async def test_expired_lease_is_fenced_and_resumes_only_durable_checkpoints(engine, artifacts_database, object_store):
    files, request = await setup(engine, artifacts_database['project_id'], object_store)
    job = await execute(engine, 'request', request)
    await execute(engine, 'deliver', 50)
    first = await execute(engine, 'claim', ClaimProcessingJob('old'))
    await execute(engine, 'checkpoint', WorkerPhase(first, stage='verify_original', checkpoint={'verified': True}))
    async with ArtifactsUnitOfWork(engine) as uow:
        row = await uow.session.get(ProcessingJobModel, job.id)
        row.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    second = await execute(engine, 'claim', ClaimProcessingJob('new'))
    assert second.fencing_token == first.fencing_token + 1
    assert second.checkpoints == {'verify_original': {'verified': True}}
    with pytest.raises(ProcessingLeaseLost):
        await execute(engine, 'checkpoint', WorkerPhase(first, stage='stale', checkpoint={'bad': True}))
    assert not await execute(engine, 'finish', WorkerPhase(first, status='failed', error_code='stale'))
    assert await execute(engine, 'heartbeat', WorkerPhase(second))
    assert await execute(engine, 'finish', WorkerPhase(second, status='failed', error_code='PROCESSOR_UNAVAILABLE'))


async def test_cancel_before_claim_is_confirmed_and_expired_owned_cancellation_is_uncertain(engine, artifacts_database, object_store):
    files, request = await setup(engine, artifacts_database['project_id'], object_store)
    job = await execute(engine, 'request', request)
    cancelled = await execute(engine, 'cancel', read_request(request, job))
    assert cancelled.status == 'cancelled'
    newer = replace(request, definition=request.definition.model_copy(update={'operation_id': uuid4().hex}))
    active = await execute(engine, 'request', newer)
    await execute(engine, 'deliver', 50)
    lease = await execute(engine, 'claim', ClaimProcessingJob('owner'))
    assert lease.id == active.id
    pending = await execute(engine, 'cancel', read_request(newer, active))
    assert pending.status == 'cancel_requested'
    async with ArtifactsUnitOfWork(engine) as uow:
        row = await uow.session.get(ProcessingJobModel, active.id)
        row.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    assert await execute(engine, 'claim', ClaimProcessingJob('reconciler')) is None
    assert (await execute(engine, 'read', read_request(newer, active))).status == 'uncertain'
    assert not await execute(engine, 'heartbeat', WorkerPhase(lease))
    # Only a finishing owner can acknowledge stopped I/O; expiry alone did not.
    assert await execute(engine, 'finish', WorkerPhase(lease, status='cancelled'))
    assert (await execute(engine, 'read', read_request(newer, active))).status == 'cancelled'


def runner(engine, store, *, checkpoint_wrapper=None, registry=None, pipeline=None):
    from modules.artifacts.application.services.processing_runner import ProcessingRunner

    def handler(method):
        async def call(request):
            return await execute(engine, method, request, registry=registry)
        return checkpoint_wrapper(call) if method == 'checkpoint' and checkpoint_wrapper else call
    return ProcessingRunner(*(handler(method) for method in ('deliver','claim','prepare','heartbeat','checkpoint','finish')),
        lambda profile: store, lease_seconds=3, pipeline=pipeline)


async def test_actual_existing_worker_runner_verifies_original_and_completes_without_a_broker(engine, artifacts_database, object_store, monkeypatch):
    from woobe_workers.settings import WorkerSettings
    from woobe_workers.consumers.artifacts import registry

    files, request = await setup(engine, artifacts_database['project_id'], object_store)
    job = await execute(engine, 'request', request)
    coordinator = runner(engine, object_store)
    monkeypatch.setattr(registry, 'build_processing_runner', lambda engine, settings: coordinator)
    registered = registry.ArtifactsWorkerRegistry()
    settings = WorkerSettings.model_validate({})
    registry.register_artifacts_workers(registered, settings, engine, rabbitmq_manager=None)
    assert len(registered.iter_workers()) == 1
    await registered.iter_workers()[0].run()
    complete = await execute(engine, 'read', read_request(request, job))
    assert complete.status == 'succeeded' and complete.result.mode == 'store_only'
    assert not complete.result.processing_performed
    assert complete.completed_stages == ('verify_original',)


async def test_lost_checkpoint_ack_resumes_without_repeating_verified_io(engine, artifacts_database, object_store):
    files, request = await setup(engine, artifacts_database['project_id'], object_store)
    job = await execute(engine, 'request', request)
    calls = []

    class CountStorage:
        async def stat(self, key):
            calls.append(key)
            return await object_store.stat(key)

    def lose_ack(handler):
        async def call(command):
            await handler(command)
            raise ConnectionError('injected after durable checkpoint commit')
        return call

    await runner(engine, CountStorage(), checkpoint_wrapper=lose_ack).run_once('first')
    retried = await execute(engine, 'read', read_request(request, job))
    assert retried.status == 'queued' and retried.completed_stages == ('verify_original',)
    async with ArtifactsUnitOfWork(engine) as uow:
        row = await uow.session.get(ProcessingJobModel, job.id)
        row.available_at = datetime.now(UTC) - timedelta(seconds=1)
    await runner(engine, CountStorage()).run_once('restarted-worker')
    complete = await execute(engine, 'read', read_request(request, job))
    assert complete.status == 'succeeded' and complete.attempt == 2
    assert len(calls) == 1


async def test_cancel_during_owned_io_awaits_cleanup_and_revoke_is_permanent(engine, artifacts_database, object_store):
    files, request = await setup(engine, artifacts_database['project_id'], object_store)
    job = await execute(engine, 'request', request)
    entered, stopped = asyncio.Event(), asyncio.Event()

    class PausedStorage:
        async def stat(self, key):
            assert engine.pool.checkedout() == 0
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

    task = asyncio.create_task(runner(engine, PausedStorage()).run_once('paused-owner'))
    await asyncio.wait_for(entered.wait(), timeout=5)
    pending = await execute(engine, 'cancel', read_request(request, job))
    assert pending.status == 'cancel_requested'
    await asyncio.wait_for(task, timeout=5)
    assert stopped.is_set()
    assert (await execute(engine, 'read', read_request(request, job))).status == 'cancelled'
    newer = replace(request, definition=request.definition.model_copy(update={'operation_id': uuid4().hex}))
    second = await execute(engine, 'request', newer)
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text("UPDATE core.api_keys SET status='revoked' WHERE id=:id"), {'id': request.principal.api_key_id})
    await runner(engine, object_store).run_once('after-revoke')
    async with ArtifactsUnitOfWork(engine) as uow:
        row = await uow.session.get(ProcessingJobModel, second.id)
        assert row.status == 'failed' and not row.retryable and row.error_code == 'ARTIFACT_ACCESS_DENIED'


async def test_project_and_workspace_budgets_do_not_allow_a_single_workspace_to_monopolize(engine, artifacts_database, object_store):
    pairs = []
    for _ in range(3):
        files, request = await setup(engine, artifacts_database['project_id'], object_store)
        for _ in range(3):
            current = replace(request, definition=request.definition.model_copy(update={'operation_id': uuid4().hex}))
            pairs.append((current, await execute(engine, 'request', current)))
    await execute(engine, 'deliver', 50)
    leases = []
    for index in range(3):
        value = await execute(engine, 'claim', ClaimProcessingJob(f'budget-{index}', project_limit=2, workspace_limit=1))
        if value is not None:
            leases.append(value)
    assert len(leases) == 2 and len({lease.workspace_id for lease in leases}) == 2
    assert await execute(engine, 'claim', ClaimProcessingJob('full-budget', project_limit=2, workspace_limit=1)) is None
    for lease in leases:
        await execute(engine, 'finish', WorkerPhase(lease, status='failed', error_code='PROCESSOR_UNAVAILABLE'))
    for request, job in pairs:
        await execute(engine, 'cancel', read_request(request, job))


async def test_request_rollback_never_leaves_an_outbox_without_its_job(engine, artifacts_database, object_store):
    files, request = await setup(engine, artifacts_database['project_id'], object_store)
    from modules.artifacts.application.contracts.processing import ProcessingRecipe
    from modules.artifacts.domain.models import ArtifactRef

    with pytest.raises(RuntimeError):
        async with ArtifactsUnitOfWork(engine) as uow:
            source = await CatalogRepository(uow).revision(request.scope, request.workspace_id,
                ArtifactRef(request.artifact_id, request.definition.revision_id))
            unpublished = await ProcessingJobRepository(uow).request(request, source, ProcessingRecipe(), None, None)
            raise RuntimeError('injected before transaction commit')
    async with ArtifactsUnitOfWork(engine) as uow:
        assert await uow.session.scalar(select(func.count()).select_from(ProcessingJobModel).where(
            ProcessingJobModel.workspace_id == request.workspace_id)) == 0
        assert not await uow.session.scalar(select(ArtifactProcessingOutboxModel.id).where(
            ArtifactProcessingOutboxModel.payload['job_id'].astext == unpublished.id))


@pytest.mark.parametrize('crash_at', ['before_checkpoint', 'after_checkpoint'])
async def test_real_worker_process_death_preserves_only_committed_checkpoints(engine, artifacts_database, object_store, crash_at, tmp_path):
    import json
    import os
    import subprocess
    import sys
    from shared.infra.object_storage.local import LocalObjectStorage

    files, request = await setup(engine, artifacts_database['project_id'], object_store)
    job = await execute(engine, 'request', request)
    configuration = {'database_url': artifacts_database['url'], 'job_id': job.id, 'crash_at': crash_at}
    if isinstance(object_store, LocalObjectStorage):
        configuration.update(kind='local', root=str(object_store._base_dir))
    else:
        configuration.update(kind='s3', bucket=object_store._bucket, prefix=object_store._prefix)
    filename = tmp_path / 'private-worker-fixture.json'
    filename.write_text(json.dumps(configuration))
    filename.chmod(0o600)
    script = '''
import asyncio, json, os, sys
from sqlalchemy.ext.asyncio import create_async_engine
from modules.artifacts.application.contracts.jobs import ClaimProcessingJob, WorkerPhase
from shared.infra.object_storage.local import LocalObjectStorage
from tests.integration.artifacts.test_jobs_postgres import execute

async def main():
    config=json.load(open(sys.argv[1]))
    engine=create_async_engine(config['database_url'], hide_parameters=True)
    if config['kind']=='local':
        store=LocalObjectStorage(config['root'])
    else:
        import botocore.session
        from botocore.config import Config
        from shared.infra.object_storage.s3 import S3ObjectStorage
        credentials=json.load(open(os.environ['WOOBE_ARTIFACT_TEST_S3_CONFIG_FILE']))
        session=botocore.session.Session()
        session.get_component('config_store').set_config_variable('profile',None)
        session.set_credentials(credentials['access_key'],credentials['secret_key'])
        client=session.create_client('s3',endpoint_url=credentials['endpoint'],region_name='us-east-1',
            config=Config(signature_version='s3v4',s3={'addressing_style':'path'}))
        store=S3ObjectStorage(client,bucket=config['bucket'],prefix=config['prefix'])
    await execute(engine,'deliver',50)
    lease=await execute(engine,'claim',ClaimProcessingJob('terminated-process'))
    assert lease.id==config['job_id']
    prepared=await execute(engine,'prepare',WorkerPhase(lease))
    actual=await store.stat(prepared['source'].object_key)
    if config['crash_at']=='after_checkpoint':
        await execute(engine,'checkpoint',WorkerPhase(lease,stage='verify_original',checkpoint={
            'sha256':actual.sha256,'size_bytes':actual.size_bytes,'version_id':actual.version_id}))
    os._exit(73)
asyncio.run(main())
'''
    process = await asyncio.to_thread(subprocess.run, [sys.executable, '-c', script, str(filename)],
        env=os.environ.copy(), capture_output=True, text=True, timeout=30)
    assert process.returncode == 73, process.stderr
    async with ArtifactsUnitOfWork(engine) as uow:
        row = await uow.session.get(ProcessingJobModel, job.id)
        row.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    calls = []

    class CountStorage:
        async def stat(self, key):
            calls.append(key)
            return await object_store.stat(key)

    await runner(engine, CountStorage()).run_once('replacement-process')
    complete = await execute(engine, 'read', read_request(request, job))
    assert complete.status == 'succeeded' and complete.attempt == 2
    assert len(calls) == (0 if crash_at == 'after_checkpoint' else 1)


async def test_single_worker_rotates_projects_and_workspaces_instead_of_draining_one_fifo(engine, artifacts_database, object_store):
    from uuid import UUID

    first_files, first = await setup(engine, artifacts_database['project_id'], object_store)
    second_files, second = await setup(engine, artifacts_database['project_id'], object_store)
    other_project = str(uuid4())
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text("INSERT INTO core.projects(id,workspace_id,name,slug,status,data) VALUES (:id,:workspace,'Fair queue project',:slug,'active','{}')"),
            {'id': UUID(other_project), 'workspace': uuid4(), 'slug': 'fair-' + uuid4().hex})
    other_files, other = await setup(engine, other_project, object_store)
    pairs = []
    for current in (first, replace(first, definition=first.definition.model_copy(update={'operation_id': uuid4().hex})), second, other):
        pairs.append((current, await execute(engine, 'request', current)))
    await execute(engine, 'deliver', 50)
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text('UPDATE artifacts.processing_project_queue SET last_claim_at=NULL WHERE project_id IN (:first,:second)'),
            {'first': UUID(first.scope.project_id), 'second': UUID(other_project)})
    selected = []
    for index in range(3):
        lease = await execute(engine, 'claim', ClaimProcessingJob(f'single-slot-{index}'))
        assert lease is not None
        selected.append(lease)
        await execute(engine, 'finish', WorkerPhase(lease, status='failed', error_code='PROCESSOR_UNAVAILABLE'))
    assert selected[0].workspace_id == first.workspace_id
    assert selected[1].scope.project_id == other_project
    assert selected[2].workspace_id == second.workspace_id
    for current, job in pairs:
        await execute(engine, 'cancel', read_request(current, job))


async def test_admission_limits_bound_pending_jobs_but_do_not_break_idempotent_replay(engine, artifacts_database, object_store):
    files, first = await setup(engine, artifacts_database['project_id'], object_store)
    other_files, second = await setup(engine, artifacts_database['project_id'], object_store)
    third_files, third = await setup(engine, artifacts_database['project_id'], object_store)

    async def admit(request):
        return await execute(engine, 'request', request, project_max_jobs=2, workspace_max_jobs=1)

    one = await admit(first)
    assert (await admit(first)).id == one.id
    next_first = replace(first, definition=first.definition.model_copy(update={'operation_id': uuid4().hex}))
    with pytest.raises(ArtifactError) as failure:
        await admit(next_first)
    assert failure.value.code == 'ARTIFACT_LIMIT_EXCEEDED' and failure.value.retryable
    two = await admit(second)
    with pytest.raises(ArtifactError):
        await admit(third)
    await execute(engine, 'cancel', read_request(first, one))
    reopened = await admit(next_first)
    await execute(engine, 'cancel', read_request(next_first, reopened))
    await execute(engine, 'cancel', read_request(second, two))


async def test_coordinator_never_reexecutes_a_durably_checkpointed_extraction_stage(engine, artifacts_database, object_store):
    import hashlib
    import json
    from modules.artifacts.application.contracts.processing import ComponentReference, ProcessingRecipe, ProfileCreate, ProfileDefault
    from modules.artifacts.application.ports.processing import ProcessingStage
    from modules.artifacts.application.processing_registry import ComponentDescriptor
    from shared.contracts.object_storage import read_bounded

    files, request = await setup(engine, artifacts_database['project_id'], object_store)
    registry = ProcessingRegistry((ComponentDescriptor('fixture-extraction', '1', 'processor', 'original',
        'canonical', frozenset({'text/plain'}), available=True),))
    recipe = ProcessingRecipe(mode='extract', processor=ComponentReference(name='fixture-extraction', version='1'))
    profile_id = uuid4().hex
    async with ArtifactsUnitOfWork(engine) as uow:
        await ProfileRepository(uow).create(request.scope, ProfileCreate(id=profile_id, revision=1, recipe=recipe))
        await ProfileRepository(uow).bind(request.scope, request.workspace_id,
            ProfileDefault(expected_version=1, profile_id=profile_id, profile_revision=1))
    job = await execute(engine, 'request', request, registry=registry)
    calls = []

    class FixturePipeline:
        async def extract(self, context):
            calls.append(context.lease.fencing_token)
            original = await read_bounded(context.storage, context.source.object_key, max_bytes=1024)
            payload = json.dumps({'orchestration_fixture': original.decode('utf-8')}).encode()
            key = f'processing/{context.lease.id}/{context.lease.fencing_token}/fixture.json'
            metadata = await context.storage.put(key, chunks(payload), size_bytes=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(), content_type='application/json')
            return {'key': key, 'sha256': metadata.sha256, 'size_bytes': metadata.size_bytes}

        def stages(self, recipe):
            return (ProcessingStage('extract', self.extract),)

        def result(self, context):
            return ProcessingJobResult(mode='extract', processing_performed=True,
                source_sha256=context.source.sha256, coverage='partial', diagnostics=('orchestration_fixture',))

    async def chunks(value):
        yield value

    def lose_extract_ack(handler):
        async def call(command):
            await handler(command)
            if command.stage == 'extract':
                raise ConnectionError('injected after extraction checkpoint commit')
        return call

    await runner(engine, object_store, checkpoint_wrapper=lose_extract_ack,
                 registry=registry, pipeline=FixturePipeline()).run_once('extract-first')
    async with ArtifactsUnitOfWork(engine) as uow:
        row = await uow.session.get(ProcessingJobModel, job.id)
        assert row.status == 'queued' and 'extract' in row.checkpoints
        row.available_at = datetime.now(UTC) - timedelta(seconds=1)
    await runner(engine, object_store, registry=registry, pipeline=FixturePipeline()).run_once('extract-restarted')
    complete = await execute(engine, 'read', read_request(request, job), registry=registry)
    assert complete.status == 'succeeded' and calls == [1]


async def test_transient_storage_failure_has_a_finite_attempt_budget(engine, artifacts_database, object_store):
    from shared.contracts.object_storage import ObjectStorageError

    files, request = await setup(engine, artifacts_database['project_id'], object_store)
    job = await execute(engine, 'request', request)
    calls = []

    class UnavailableStorage:
        async def stat(self, key):
            calls.append(key)
            raise ObjectStorageError('unavailable', 'injected backend timeout')

    for index in range(3):
        await runner(engine, UnavailableStorage()).run_once('retry-' + str(index))
        async with ArtifactsUnitOfWork(engine) as uow:
            row = await uow.session.get(ProcessingJobModel, job.id)
            row.available_at = datetime.now(UTC) - timedelta(seconds=1)
    complete = await execute(engine, 'read', read_request(request, job))
    assert complete.status == 'failed' and complete.attempt == 3 and not complete.retryable
    assert complete.error_code == 'ARTIFACT_STORAGE_UNAVAILABLE'
    assert len(calls) == 3
    assert await runner(engine, UnavailableStorage()).run_once('no-endless-retry') is None


async def test_public_background_factory_uses_the_worker_owned_engine_and_phase_wiring(engine, artifacts_database, object_store, monkeypatch):
    from modules.artifacts.background_boundary import build_processing_runner
    from modules.artifacts.composition import processing
    from woobe_workers.settings import WorkerSettings

    files, request = await setup(engine, artifacts_database['project_id'], object_store)
    job = await execute(engine, 'request', request)
    monkeypatch.setattr(processing, 'upload_storage', lambda profile: object_store)
    coordinator = build_processing_runner(engine, WorkerSettings.model_validate({}))
    await coordinator.run_once('public-background-factory')
    complete = await execute(engine, 'read', read_request(request, job))
    assert complete.status == 'succeeded' and complete.result.processing_performed is False


async def test_native_extraction_real_background_factory_resumes_committed_canonical_without_reparse(engine, artifacts_database, object_store, monkeypatch):
    from modules.artifacts.application.contracts.processing import ComponentReference, ProcessingRecipe, ProfileCreate, ProfileDefault
    from modules.artifacts.application.document_codec import decode_canonical
    from modules.artifacts.background_boundary import build_processing_runner
    from modules.artifacts.composition import processing
    from modules.artifacts.infra.processing.native_text import NativeTextProcessor
    from shared.contracts.object_storage import read_bounded
    from woobe_workers.settings import WorkerSettings

    files, request = await setup(engine, artifacts_database['project_id'], object_store)
    registry = processing.PROCESSING_REGISTRY
    recipe = registry.normalize(ProcessingRecipe(mode='extract', processor=ComponentReference(name='native-text', version='1')))
    profile_id = uuid4().hex
    async with ArtifactsUnitOfWork(engine) as uow:
        await ProfileRepository(uow).create(request.scope, ProfileCreate(id=profile_id, revision=1, recipe=recipe))
        await ProfileRepository(uow).bind(request.scope, request.workspace_id,
            ProfileDefault(expected_version=1, profile_id=profile_id, profile_revision=1))
    job = await execute(engine, 'request', request, registry=registry)
    calls = []
    original = NativeTextProcessor.process

    async def counted(self, *args, **kwargs):
        calls.append(True)
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(NativeTextProcessor, 'process', counted)
    monkeypatch.setattr(processing, 'upload_storage', lambda profile: object_store)
    phase = processing._worker_phase

    def lose_ack(engine, settings, method):
        handler = phase(engine, settings, method)
        async def wrapped(command):
            result = await handler(command)
            if method == 'checkpoint' and command.stage == 'extract':
                raise ConnectionError('injected after durable native extraction checkpoint')
            return result
        return wrapped

    monkeypatch.setattr(processing, '_worker_phase', lose_ack)
    await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('native-first')
    async with ArtifactsUnitOfWork(engine) as uow:
        row = await uow.session.get(ProcessingJobModel, job.id)
        assert row.status == 'queued'
        checkpoint = row.checkpoints['extract']
        row.available_at = datetime.now(UTC) - timedelta(seconds=1)
    canonical_bytes = await read_bounded(object_store, checkpoint['key'], max_bytes=1_048_576)
    import hashlib
    assert hashlib.sha256(canonical_bytes).hexdigest() == checkpoint['sha256']
    document = decode_canonical(canonical_bytes)
    assert document.blocks[0].text == 'Texto com acentuação\n'
    assert document.page_count is None
    from modules.artifacts.infra.database.models import RevisionModel
    async with ArtifactsUnitOfWork(engine) as uow:
        source = await uow.session.get(RevisionModel, request.definition.revision_id)
        source_key = source.object_key
    locator = document.blocks[0].locator
    stream = object_store.open(source_key, start=locator.byte_start, end=locator.byte_end)
    try:
        ranged = b''.join([chunk async for chunk in stream])
    finally:
        await stream.aclose()
    assert ranged.decode('utf-8') == document.blocks[0].text
    monkeypatch.setattr(processing, '_worker_phase', phase)
    await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('native-resumed')
    complete = await execute(engine, 'read', read_request(request, job), registry=registry)
    assert complete.status == 'succeeded' and complete.result.processing_performed
    assert set(complete.completed_stages) == {'verify_original', 'extract'} and len(calls) == 1
    assert complete.result.source_sha256 == checkpoint['source_sha256']
