import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from modules.artifacts.application.authorization import ArtifactAuthorization, principal_identity
from modules.artifacts.application.contracts.api import UploadCreate
from modules.artifacts.application.contracts.uploads import BeginUpload, UploadPart, UploadRequest
from modules.artifacts.application.contracts.workspaces import CreateWorkspace
from modules.artifacts.application.services.uploads import UploadService
from modules.artifacts.application.use_cases.uploads import UploadUseCases
from modules.artifacts.domain.models import Action, ArtifactError, WorkspaceGrant
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.models import ArtifactEventModel, RevisionModel, UploadModel, WorkspaceModel
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from modules.artifacts.infra.database.uploads import UploadRepository
from shared.infra.object_storage.local import LocalObjectStorage
from shared.infra.object_storage.s3 import S3ObjectStorage
from shared.infra.transactional_handler import TransactionalHandler
from tests.integration.artifacts.test_workspaces_postgres import execute, prepare_namespace


@pytest.fixture(params=['local', 's3'])
def object_store(request, tmp_path):
    if request.param == 'local':
        return LocalObjectStorage(tmp_path / 'objects')
    client, bucket = request.getfixturevalue('s3_backend')
    return S3ObjectStorage(client, bucket=bucket, prefix=uuid4().hex)


def service(engine, store, *, commit_wrapper=None):
    def handler(method):
        uow = ArtifactsUnitOfWork(engine)
        grants = GrantRepository(uow)
        use_cases = UploadUseCases(UploadRepository(uow),
            ArtifactAuthorization(ExistingPrincipalAuthority(uow), grants), max_upload_bytes=32 * 1024 * 1024)
        result = TransactionalHandler(uow, getattr(use_cases, method))
        return commit_wrapper(result) if method == 'commit' and commit_wrapper else result
    return UploadService(*(handler(name) for name in ('begin', 'status', 'admit', 'record', 'verify', 'commit', 'abort')),
                         storage=lambda profile: store)


async def setup(engine, project, store, content=b'hello upload', quota=1024):
    actor, scope, definition = await prepare_namespace(engine, project)
    definition = definition.model_copy(update={'quota_bytes': quota})
    workspace = await execute(engine, 'create', CreateWorkspace(actor, scope, definition))
    api = service(engine, store)
    begin = BeginUpload(actor, scope, workspace.id, UploadCreate(operation_id=str(uuid4()),
        path='folder/data.txt', size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest(), content_type='text/plain'))
    view = await api.begin(begin)
    request = UploadRequest(actor, scope, workspace.id, view.id)
    return api, begin, request


def part(request, offset, content):
    return UploadPart(request.principal, request.scope, request.workspace_id, request.upload_id, offset, content)


async def accounting(engine, workspace_id):
    async with ArtifactsUnitOfWork(engine) as uow:
        workspace = await uow.session.get(WorkspaceModel, workspace_id)
        return workspace.used_bytes, workspace.reserved_bytes, workspace.catalog_version


async def test_resume_replay_durable_receipt_and_transactional_event(engine, artifacts_database, object_store):
    content = b'hello upload'
    api, begin, request = await setup(engine, artifacts_database['project_id'], object_store, content)
    assert (await api.begin(begin)).id == request.upload_id
    assert await accounting(engine, request.workspace_id) == (0, len(content), 0)
    assert (await api.append(part(request, 0, content[:5]))).offset == 5
    # A new service instance resumes persisted state, with identical-part ACK replay.
    api = service(engine, object_store)
    assert (await api.append(part(request, 0, content[:5]))).offset == 5
    with pytest.raises(ArtifactError) as failure:
        await api.append(part(request, 0, b'wrong'))
    assert failure.value.code == 'UPLOAD_OFFSET_CONFLICT'
    with pytest.raises(ArtifactError):
        await api.finalize(request)
    await api.append(part(request, 5, content[5:]))
    receipt, replay = await asyncio.gather(api.finalize(request), service(engine, object_store).finalize(request))
    assert receipt.receipt == replay.receipt and receipt.status == 'committed'
    assert await accounting(engine, request.workspace_id) == (len(content), 0, 1)
    async with ArtifactsUnitOfWork(engine) as uow:
        assert await uow.session.scalar(select(func.count()).select_from(RevisionModel).where(RevisionModel.workspace_id == request.workspace_id)) == 1
        assert await uow.session.scalar(select(func.count()).select_from(ArtifactEventModel).where(ArtifactEventModel.workspace_id == request.workspace_id)) == 1
    assert (await api.abort(request)).receipt == receipt.receipt
    assert (await api.begin(begin)).receipt == receipt.receipt
    with pytest.raises(ArtifactError) as failure:
        await api.begin(replace(begin, definition=begin.definition.model_copy(update={'path': 'other.txt'})))
    assert failure.value.code == 'ARTIFACT_IDEMPOTENCY_CONFLICT'


async def test_lost_commit_ack_recovers_same_receipt_after_real_commit(engine, artifacts_database, object_store):
    api, begin, request = await setup(engine, artifacts_database['project_id'], object_store)
    await api.append(part(request, 0, b'hello upload'))
    def lose_ack(handler):
        async def call(command):
            await handler(command)
            raise ConnectionError('injected after committed transaction')
        return call
    with pytest.raises(ConnectionError):
        await service(engine, object_store, commit_wrapper=lose_ack).finalize(request)
    recovered = await service(engine, object_store).finalize(request)
    assert recovered.receipt is not None
    assert await accounting(engine, request.workspace_id) == (12, 0, 1)


async def test_quota_reservations_compete_and_abort_expiry_release_exactly_once(engine, artifacts_database, object_store):
    api, begin, request = await setup(engine, artifacts_database['project_id'], object_store, b'12345', quota=10)
    other = replace(begin, definition=begin.definition.model_copy(update={'operation_id': str(uuid4()), 'path': 'other.txt', 'size_bytes': 6}))
    with pytest.raises(ArtifactError) as failure:
        await api.begin(other)
    assert failure.value.code == 'QUOTA_EXCEEDED'
    await asyncio.gather(api.abort(request), service(engine, object_store).abort(request))
    assert await accounting(engine, request.workspace_id) == (0, 0, 0)
    candidates = [replace(other, definition=other.definition.model_copy(update={'operation_id': str(uuid4())})) for _ in range(2)]
    results = await asyncio.gather(*(service(engine, object_store).begin(candidate) for candidate in candidates), return_exceptions=True)
    assert sum(isinstance(value, ArtifactError) and value.code == 'QUOTA_EXCEEDED' for value in results) == 1
    winner = next(value for value in results if not isinstance(value, Exception))
    expired_request = replace(request, upload_id=winner.id)
    async with ArtifactsUnitOfWork(engine) as uow:
        row = await uow.session.get(UploadModel, winner.id)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert (await api.status(expired_request)).status == 'expired'
    assert (await api.status(expired_request)).status == 'expired'
    assert await accounting(engine, request.workspace_id) == (0, 0, 0)


async def test_status_resume_and_finalize_deny_other_subject_workspace_and_revoked_grant(engine, artifacts_database, object_store):
    api, begin, request = await setup(engine, artifacts_database['project_id'], object_store)
    other, other_scope, _ = await prepare_namespace(engine, artifacts_database['project_id'])
    async with ArtifactsUnitOfWork(engine) as uow:
        await GrantRepository(uow).add(WorkspaceGrant(str(uuid4()), principal_identity(other),
            request.scope, frozenset(Action), workspace_id=request.workspace_id))
    for invalid in (replace(request, principal=other), replace(request, workspace_id=str(uuid4())),
                    replace(request, scope=replace(other_scope, environment='production'))):
        for operation in (api.status, api.finalize, api.abort):
            with pytest.raises(ArtifactError) as failure:
                await operation(invalid)
            assert failure.value.code == 'ARTIFACT_ACCESS_DENIED'
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text('UPDATE artifacts.grants SET revoked=true WHERE principal_id=:subject'),
                                  {'subject': principal_identity(request.principal)})
    with pytest.raises(ArtifactError):
        await api.append(part(request, 0, b'hello upload'))


@pytest.mark.parametrize('content,declared', [(b'bad hash', 'text/plain'), (b'%PDF-1.7\n', 'image/png')])
async def test_invalid_checksum_or_media_never_publishes_revision(engine, artifacts_database, object_store, content, declared):
    api, begin, request = await setup(engine, artifacts_database['project_id'], object_store, content)
    # Change metadata before a new intent; the original reservation is released.
    await api.abort(request)
    changed = begin.definition.model_copy(update={'operation_id': str(uuid4()), 'content_type': declared,
        'sha256': '0' * 64 if content == b'bad hash' else hashlib.sha256(content).hexdigest()})
    view = await api.begin(replace(begin, definition=changed))
    request = replace(request, upload_id=view.id)
    await api.append(part(request, 0, content))
    with pytest.raises(ArtifactError) as failure:
        await api.finalize(request)
    assert failure.value.code == 'UPLOAD_INTEGRITY_MISMATCH'
    assert await accounting(engine, request.workspace_id) == (0, len(content), 0)
    await api.abort(request)
    assert await accounting(engine, request.workspace_id) == (0, 0, 0)


async def test_two_updates_of_same_revision_have_one_cas_winner_and_release_loser(engine, artifacts_database, object_store):
    api, begin, request = await setup(engine, artifacts_database['project_id'], object_store)
    await api.append(part(request, 0, b'hello upload'))
    original = await api.finalize(request)
    commands = [replace(begin, definition=begin.definition.model_copy(update={
        'operation_id': str(uuid4()), 'artifact_id': original.receipt.artifact_id,
        'expected_revision': original.receipt.revision_id,
    })) for _ in range(2)]
    views = [await api.begin(command) for command in commands]
    requests = [replace(request, upload_id=view.id) for view in views]
    for current in requests:
        await api.append(part(current, 0, b'hello upload'))
    results = await asyncio.gather(*(service(engine, object_store).finalize(current) for current in requests), return_exceptions=True)
    assert sum(isinstance(result, ArtifactError) and result.code == 'ARTIFACT_REVISION_CONFLICT' for result in results) == 1
    loser = requests[next(index for index, result in enumerate(results) if isinstance(result, ArtifactError))]
    assert await accounting(engine, request.workspace_id) == (24, 12, 2)
    await api.abort(loser)
    assert await accounting(engine, request.workspace_id) == (24, 0, 2)


async def test_abort_during_storage_io_wins_and_no_database_connection_is_held(engine, artifacts_database, object_store):
    api, begin, request = await setup(engine, artifacts_database['project_id'], object_store)
    await api.append(part(request, 0, b'hello upload'))
    entered, proceed = asyncio.Event(), asyncio.Event()

    class PausedStorage:
        async def put(self, *args, **kwargs):
            assert engine.pool.checkedout() == 0
            entered.set()
            await proceed.wait()
            return await object_store.put(*args, **kwargs)

        def open(self, *args, **kwargs):
            assert engine.pool.checkedout() == 0
            return object_store.open(*args, **kwargs)

    operation = asyncio.create_task(service(engine, PausedStorage()).finalize(request))
    await entered.wait()
    assert (await api.abort(request)).status == 'aborted'
    proceed.set()
    with pytest.raises(ArtifactError) as failure:
        await operation
    assert failure.value.code == 'UPLOAD_EXPIRED'
    assert await accounting(engine, request.workspace_id) == (0, 0, 0)
    async with ArtifactsUnitOfWork(engine) as uow:
        assert await uow.session.scalar(select(func.count()).select_from(ArtifactEventModel).where(ArtifactEventModel.workspace_id == request.workspace_id)) == 0


async def test_concurrent_parts_have_one_offset_winner_and_empty_upload_is_durable(engine, artifacts_database, object_store):
    api, begin, request = await setup(engine, artifacts_database['project_id'], object_store, b'hello upload')
    results = await asyncio.gather(service(engine, object_store).append(part(request, 0, b'hello')),
        service(engine, object_store).append(part(request, 0, b'world')), return_exceptions=True)
    assert sum(isinstance(result, ArtifactError) and result.code == 'UPLOAD_OFFSET_CONFLICT' for result in results) == 1
    assert (await api.status(request)).offset == 5
    await api.abort(request)
    empty = replace(begin, definition=begin.definition.model_copy(update={
        'operation_id': str(uuid4()), 'size_bytes': 0, 'sha256': hashlib.sha256(b'').hexdigest()}))
    view = await api.begin(empty)
    empty_request = replace(request, upload_id=view.id)
    receipt = await api.finalize(empty_request)
    assert receipt.receipt == (await api.finalize(empty_request)).receipt
    assert await accounting(engine, request.workspace_id) == (0, 0, 1)


async def test_cancelled_part_after_storage_ack_resumes_without_new_reservation(engine, artifacts_database, object_store):
    api, begin, request = await setup(engine, artifacts_database['project_id'], object_store)

    class CancelAfterStore:
        async def put(self, *args, **kwargs):
            await object_store.put(*args, **kwargs)
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await service(engine, CancelAfterStore()).append(part(request, 0, b'hello upload'))
    assert (await api.status(request)).offset == 0
    assert await accounting(engine, request.workspace_id) == (0, 12, 0)
    await service(engine, object_store).append(part(request, 0, b'hello upload'))
    assert (await api.finalize(request)).receipt is not None
    assert await accounting(engine, request.workspace_id) == (12, 0, 1)
