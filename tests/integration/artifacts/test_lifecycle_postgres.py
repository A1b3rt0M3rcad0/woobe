from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import select

from modules.artifacts.application.contracts.uploads import UploadRequest
from modules.artifacts.domain.models import ArtifactError, ArtifactRef, artifact_object_key
from modules.artifacts.infra.database.files import FileRepository
from modules.artifacts.infra.database.lifecycle import ArtifactLifecycleRepository
from modules.artifacts.infra.database.models import ArtifactEventModel, GrantModel, RevisionModel, UploadModel, WorkspaceModel
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from modules.artifacts.application.contracts.files import ReadFile
from modules.artifacts.application.contracts.api import UploadCreate
from shared.contracts.object_storage import ObjectStorageError
from shared.infra.object_storage.local import LocalObjectStorage
from tests.integration.artifacts.test_uploads_postgres import part, setup


async def read_revision(engine, principal, scope, workspace_id, artifact_id, revision_id):
    async with ArtifactsUnitOfWork(engine) as uow:
        return await FileRepository(uow).read(ReadFile(
            principal, scope, workspace_id, artifact_id, revision_id,
        ))


async def test_archived_workspace_retention_transitions_to_a_delayed_purge(
    engine, artifacts_database, tmp_path,
):
    store = LocalObjectStorage(tmp_path / 'objects')
    _, _, request = await setup(engine, artifacts_database['project_id'], store, b'unused')
    async with ArtifactsUnitOfWork(engine) as uow:
        workspace = await uow.session.get(WorkspaceModel, request.workspace_id)
        workspace.retention_days = 0
        workspace.status = 'archived'
        workspace.archived_at = datetime.now(UTC) - timedelta(hours=1)

    lifecycle = ArtifactLifecycleRepository(engine)
    assert await lifecycle.mark_retention_expired() == 1
    assert await lifecycle.pending_workspace_cleanup() == ()
    async with ArtifactsUnitOfWork(engine) as uow:
        workspace = await uow.session.get(WorkspaceModel, request.workspace_id)
        assert workspace.status == 'deletion_pending'
        assert workspace.deletion_requested_at is not None


async def test_multipart_reconciliation_protects_only_live_upload_intents(
    engine, artifacts_database, tmp_path,
):
    store = LocalObjectStorage(tmp_path / 'objects')
    _, _, request = await setup(engine, artifacts_database['project_id'], store, b'pending')
    lifecycle = ArtifactLifecycleRepository(engine)
    async with ArtifactsUnitOfWork(engine) as uow:
        upload = await uow.session.get(UploadModel, request.upload_id)
        key = artifact_object_key(request.scope, request.workspace_id,
            ArtifactRef(upload.artifact_id, upload.planned_revision_id))
    assert await lifecycle.multipart_upload_active(key, 'live-multipart')
    async with ArtifactsUnitOfWork(engine) as uow:
        upload = await uow.session.get(UploadModel, request.upload_id)
        upload.status = 'expired'
        upload.expires_at = datetime.now(UTC) - timedelta(hours=1)
    assert not await lifecycle.multipart_upload_active(key, 'expired-multipart')


async def test_revision_retention_is_fenced_retryable_and_never_falls_forward(
    engine, artifacts_database, tmp_path,
):
    store = LocalObjectStorage(tmp_path / 'objects')
    api, begin, request = await setup(engine, artifacts_database['project_id'], store, b'first revision')
    await api.append(part(request, 0, b'first revision'))
    first = await api.finalize(request)

    second_content = b'second current revision'
    second_definition = begin.definition.model_copy(update={
        'operation_id': str(uuid4()),
        'artifact_id': first.receipt.artifact_id,
        'expected_revision': first.receipt.revision_id,
        'size_bytes': len(second_content),
        'sha256': hashlib.sha256(second_content).hexdigest(),
    })
    second_begin = replace(begin, definition=second_definition)
    second_view = await api.begin(second_begin)
    second_request = UploadRequest(request.principal, request.scope, request.workspace_id, second_view.id)
    await api.append(part(second_request, 0, second_content))
    second = await api.finalize(second_request)

    async with ArtifactsUnitOfWork(engine) as uow:
        workspace = await uow.session.get(WorkspaceModel, request.workspace_id)
        workspace.retention_days = 0
        old_row = await uow.session.scalar(select(RevisionModel).where(
            RevisionModel.workspace_id == request.workspace_id,
            RevisionModel.id == first.receipt.revision_id,
        ))
        old_key = old_row.object_key

    lifecycle = ArtifactLifecycleRepository(engine, revision_grace=timedelta(0))
    targets = await lifecycle.due_revision_cleanup()
    assert len(targets) == 1 and targets[0].revision_id == first.receipt.revision_id
    with pytest.raises(ArtifactError) as unavailable:
        await read_revision(engine, request.principal, request.scope, request.workspace_id,
            first.receipt.artifact_id, first.receipt.revision_id)
    assert unavailable.value.code == 'SOURCE_UNAVAILABLE'

    class FailOnce:
        def __init__(self):
            self.failed = False

        async def delete(self, key):
            if not self.failed:
                self.failed = True
                raise ObjectStorageError('unavailable', 'injected failure')
            await store.delete(key)

    flaky = FailOnce()
    for key in targets[0].object_keys:
        with pytest.raises(ObjectStorageError):
            await flaky.delete(key)
        break
    retry = await lifecycle.due_revision_cleanup()
    assert len(retry) == 1 and retry[0].revision_id == first.receipt.revision_id
    for key in retry[0].object_keys:
        await store.delete(key)
    assert await lifecycle.finish_revision_cleanup(retry[0])

    with pytest.raises(ObjectStorageError):
        await store.stat(old_key)
    with pytest.raises(ArtifactError) as unavailable:
        await read_revision(engine, request.principal, request.scope, request.workspace_id,
            first.receipt.artifact_id, first.receipt.revision_id)
    assert unavailable.value.code == 'SOURCE_UNAVAILABLE'
    current = await read_revision(engine, request.principal, request.scope, request.workspace_id,
        second.receipt.artifact_id, second.receipt.revision_id)
    assert current.revision.sha256 == hashlib.sha256(second_content).hexdigest()
    async with ArtifactsUnitOfWork(engine) as uow:
        workspace = await uow.session.get(WorkspaceModel, request.workspace_id)
        old = await uow.session.get(RevisionModel, first.receipt.revision_id)
        assert old.content_state == 'purged'
        assert workspace.used_bytes == len(second_content)
        assert workspace.reserved_bytes == 0


async def test_workspace_purge_waits_for_live_upload_then_scrubs_and_converges(
    engine, artifacts_database, tmp_path,
):
    store = LocalObjectStorage(tmp_path / 'objects')
    api, begin, request = await setup(engine, artifacts_database['project_id'], store, b'workspace contents')
    await api.append(part(request, 0, b'workspace contents'))
    receipt = await api.finalize(request)
    lifecycle = ArtifactLifecycleRepository(engine)
    pending_upload = await api.begin(replace(begin, definition=UploadCreate(
        operation_id=str(uuid4()), path='waiting.txt', size_bytes=0,
        sha256=hashlib.sha256(b'').hexdigest(), content_type='text/plain',
    )))

    async with ArtifactsUnitOfWork(engine) as uow:
        upload = await uow.session.get(UploadModel, pending_upload.id)
        upload.expires_at = datetime.now(UTC) + timedelta(hours=1)
    assert await lifecycle.reconcile_restore_tombstones((request.workspace_id,)) == 1
    assert await lifecycle.pending_workspace_cleanup() == ()

    async with ArtifactsUnitOfWork(engine) as uow:
        upload = await uow.session.get(UploadModel, pending_upload.id)
        upload.status = 'aborted'

    targets = await lifecycle.pending_workspace_cleanup()
    assert len(targets) == 1
    for key in targets[0].object_keys:
        await store.delete(key)
    assert await lifecycle.finish_workspace_cleanup(targets[0])
    assert await lifecycle.pending_workspace_cleanup() == ()

    async with ArtifactsUnitOfWork(engine) as uow:
        workspace = await uow.session.get(WorkspaceModel, request.workspace_id)
        upload = await uow.session.get(UploadModel, request.upload_id)
        grant = await uow.session.scalar(select(GrantModel).where(
            GrantModel.workspace_id == request.workspace_id,
        ))
        revision = await uow.session.get(RevisionModel, receipt.receipt.revision_id)
        purge_event = await uow.session.scalar(select(ArtifactEventModel).where(
            ArtifactEventModel.workspace_id == request.workspace_id,
            ArtifactEventModel.kind == 'artifact.workspace.purged',
        ))
        assert workspace.status == 'purged'
        assert workspace.used_bytes == workspace.reserved_bytes == 0
        assert workspace.name == 'Purged Workspace'
        assert upload.parts == [] and upload.receipt is None
        assert grant is None or grant.revoked
        assert revision.content_state == 'purged' and revision.source_refs == []
        assert purge_event is not None
