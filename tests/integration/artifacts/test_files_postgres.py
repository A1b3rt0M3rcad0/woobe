import asyncio
from dataclasses import replace
import importlib
from uuid import uuid4

import pytest
from sqlalchemy import select

from modules.artifacts.application.authorization import ArtifactAuthorization
from modules.artifacts.application.contracts.files import CopyFile, ListFiles, MutateFile, ReadFile, WriteText
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.application.services.files import FileService
from modules.artifacts.application.use_cases.files import FileUseCases
from modules.artifacts.domain.models import ArtifactError
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.files import FileRepository
from modules.artifacts.infra.database.models import RevisionModel
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler
from tests.integration.artifacts.test_uploads_postgres import object_store as object_store, service as uploads, setup


def service(engine, store):
    def handler(method):
        uow = ArtifactsUnitOfWork(engine)
        grants = GrantRepository(uow)
        use_cases = FileUseCases(FileRepository(uow),
            ArtifactAuthorization(ExistingPrincipalAuthority(uow), grants), CursorCodec(b'f' * 32))
        return TransactionalHandler(uow, getattr(use_cases, method))
    return FileService(handler('read'), handler('page'), handler('mutate'),
                       uploads(engine, store), lambda profile: store)


async def prepare(engine, project, store):
    api, begin, request = await setup(engine, project, store)
    await api.abort(request)
    text = WriteText(request.principal, request.scope, request.workspace_id, str(uuid4()),
                     'docs/notes.txt', 'Texto com acentuação\n')
    return service(engine, store), text


def read(request, reference, revision=None):
    return ReadFile(request.principal, request.scope, request.workspace_id, reference.artifact_id, revision)


def mutation(request, kind, artifact=None, path=None, version=None):
    return MutateFile(request.principal, request.scope, request.workspace_id, str(uuid4()), kind,
        artifact.id if artifact else None, version if version is not None else artifact.version if artifact else None, path)


def listing(request, directory='', limit=50, cursor=None):
    return ListFiles(request.principal, request.scope, request.workspace_id, directory, limit, cursor)


async def test_text_publication_runtime_bytes_rename_history_and_editable_copy(engine, artifacts_database, object_store):
    api, command = await prepare(engine, artifacts_database['project_id'], object_store)
    receipt = await api.write_text(command)
    assert receipt.receipt == (await api.write_text(command)).receipt
    original = await api.resolve(read(command, receipt.receipt))
    assert original.revision.origin == 'application' and original.revision.operation_id == command.operation_id
    assert original.revision.run_id is None and original.revision.node_id is None
    assert await api.read_bytes(read(command, receipt.receipt)) == command.text.encode()
    renamed = await api.mutate(mutation(command, 'move', original.artifact, 'docs/renamed.txt'))
    assert renamed.id == original.artifact.id and renamed.version == 2
    assert await api.read_text(read(command, receipt.receipt, receipt.receipt.revision_id)) == command.text
    updated = await api.write_text(replace(command, operation_id=str(uuid4()), path=renamed.path,
        text='new contents', artifact_id=renamed.id, expected_revision=receipt.receipt.revision_id,
        origin='agent', run_id='run-one', node_id='node-one'))
    current = await api.resolve(read(command, updated.receipt))
    assert current.artifact.id == renamed.id and current.artifact.version == 3
    assert (current.revision.origin, current.revision.run_id, current.revision.node_id) == ('agent', 'run-one', 'node-one')
    assert await api.read_text(read(command, receipt.receipt, receipt.receipt.revision_id)) == command.text
    copied = await api.copy(CopyFile(command.principal, command.scope, command.workspace_id,
        renamed.id, current.revision.id, str(uuid4()), 'editable.txt'))
    assert copied.receipt.artifact_id != renamed.id
    assert await api.read_text(read(command, copied.receipt)) == 'new contents'
    assert (await api.resolve(read(command, copied.receipt))).revision.origin == 'copy'
    # A representation identity is never accepted as a mutable Artifact.
    with pytest.raises(ArtifactError):
        await api.write_text(replace(command, operation_id=str(uuid4()), artifact_id='immutable-representation', expected_revision='generation-one'))


async def test_logical_directory_listing_tree_move_collisions_and_nonempty_delete(engine, artifacts_database, object_store):
    api, command = await prepare(engine, artifacts_database['project_id'], object_store)
    receipt = await api.write_text(replace(command, path='tree/nested/leaf.txt'))
    root = (await api.list(listing(command))).items[0]
    assert root.kind == 'directory' and root.path == 'tree'
    nested = (await api.list(listing(command, 'tree'))).items[0]
    assert nested.kind == 'directory'
    leaf = (await api.list(listing(command, 'tree/nested'))).items[0]
    assert leaf.id == receipt.receipt.artifact_id
    with pytest.raises(ArtifactError) as failure:
        await api.mutate(mutation(command, 'delete', root))
    assert failure.value.code == 'ARTIFACT_PATH_CONFLICT'
    with pytest.raises(ArtifactError):
        await api.write_text(replace(command, operation_id=str(uuid4()), path='tree', text='cannot replace a directory'))
    with pytest.raises(ArtifactError):
        await api.mutate(mutation(command, 'mkdir', path='tree/nested/leaf.txt/child'))
    move = mutation(command, 'move', root, 'moved')
    moved = await api.mutate(move)
    assert moved == await api.mutate(move)
    assert (await api.resolve(read(command, receipt.receipt))).artifact.path == 'moved/nested/leaf.txt'
    assert (await api.list(listing(command, 'tree/nested'))).items == ()
    with pytest.raises(ArtifactError) as failure:
        await api.mutate(replace(move, path='another'))
    assert failure.value.code == 'ARTIFACT_IDEMPOTENCY_CONFLICT'
    with pytest.raises(ArtifactError):
        await api.mutate(mutation(command, 'move', moved, 'moved/nested/loop'))
    child = (await api.list(listing(command, 'moved/nested'))).items[0]
    await api.mutate(mutation(command, 'delete', child))
    with pytest.raises(ArtifactError):
        await api.resolve(read(command, receipt.receipt, receipt.receipt.revision_id))
    nested = (await api.list(listing(command, 'moved'))).items[0]
    await api.mutate(mutation(command, 'delete', nested))
    await api.mutate(mutation(command, 'delete', moved))
    assert (await api.list(listing(command))).items == ()


async def test_directory_pages_freeze_paths_and_do_not_resurrect_deleted_files(engine, artifacts_database, object_store):
    api, command = await prepare(engine, artifacts_database['project_id'], object_store)
    receipts = [await api.write_text(replace(command, operation_id=str(uuid4()), path=f'docs/{index}.txt')) for index in range(3)]
    first = await api.list(listing(command, 'docs', 1))
    assert first.has_more
    others = [receipt for receipt in receipts if receipt.receipt.artifact_id != first.items[0].id]
    moving = await api.resolve(read(command, others[0].receipt))
    deleting = await api.resolve(read(command, others[1].receipt))
    await api.mutate(mutation(command, 'move', moving.artifact, 'docs/new.txt'))
    await api.mutate(mutation(command, 'delete', deleting.artifact))
    rest = await api.list(listing(command, 'docs', 50, first.next_cursor))
    assert len(rest.items) == 1 and rest.items[0].path == moving.artifact.path
    assert not rest.has_more
    with pytest.raises(ArtifactError):
        await api.list(listing(command, '', 50, first.next_cursor))


@pytest.mark.parametrize('kind', ['move', 'delete'])
async def test_write_and_path_mutation_races_cannot_overwrite_each_other(engine, artifacts_database, object_store, kind):
    api, command = await prepare(engine, artifacts_database['project_id'], object_store)
    receipt = await api.write_text(command)
    original = await api.resolve(read(command, receipt.receipt))
    write = replace(command, operation_id=str(uuid4()), text='race update',
                    artifact_id=original.artifact.id, expected_revision=original.revision.id)
    mutate = mutation(command, kind, original.artifact, 'docs/moved.txt' if kind == 'move' else None)
    results = await asyncio.gather(service(engine, object_store).write_text(write),
        service(engine, object_store).mutate(mutate), return_exceptions=True)
    assert sum(isinstance(result, ArtifactError) for result in results) == 1
    async with ArtifactsUnitOfWork(engine) as uow:
        rows = list((await uow.session.execute(select(RevisionModel).where(
            RevisionModel.artifact_id == original.artifact.id))).scalars())
        assert len(rows) in {1, 2}
        assert next(row for row in rows if row.id == original.revision.id).sha256 == original.revision.sha256


async def test_public_composition_calls_same_authorized_file_service(engine, artifacts_database, object_store, monkeypatch):
    api, command = await prepare(engine, artifacts_database['project_id'], object_store)
    for name in ('get_file', 'list_files', 'mutate_file', 'begin_upload', 'get_upload', 'admit_upload',
                 'record_upload', 'verify_upload', 'commit_upload', 'abort_upload'):
        module = importlib.import_module('modules.artifacts.composition.composers.' + name)
        monkeypatch.setattr(module, 'DATABASE_ENGINE', engine)
    for name in ('files', 'uploads'):
        module = importlib.import_module('modules.artifacts.composition.' + name)
        monkeypatch.setattr(module, 'upload_storage', lambda profile: object_store)
    from modules.artifacts.entrypoint import build_file_service
    receipt = await build_file_service().write_text(command)
    assert await build_file_service().read_bytes(read(command, receipt.receipt)) == command.text.encode()


async def test_directory_names_with_sql_wildcards_are_literal_and_creation_is_idempotent(engine, artifacts_database, object_store):
    api, command = await prepare(engine, artifacts_database['project_id'], object_store)
    create = mutation(command, 'mkdir', path='100%_literal')
    directory = await api.mutate(create)
    assert directory == await api.mutate(create)
    with pytest.raises(ArtifactError):
        await api.mutate(replace(create, operation_id=str(uuid4())))
    literal = await api.write_text(replace(command, operation_id=str(uuid4()), path='100%_literal/one.txt'))
    await api.write_text(replace(command, operation_id=str(uuid4()), path='100XXliteral/other.txt'))
    page = await api.list(listing(command, '100%_literal'))
    assert len(page.items) == 1 and page.items[0].id == literal.receipt.artifact_id
    moved = await api.mutate(mutation(command, 'move', directory, 'renamed'))
    assert moved.id == directory.id
    assert len((await api.list(listing(command, '100XXliteral'))).items) == 1


@pytest.mark.parametrize('origin', ['tool', 'processing'])
async def test_trusted_internal_origin_is_retained_on_each_immutable_revision(engine, artifacts_database, object_store, origin):
    api, command = await prepare(engine, artifacts_database['project_id'], object_store)
    receipt = await api.write_text(replace(command, origin=origin, run_id='existing-run', node_id='existing-node'))
    snapshot = await api.resolve(read(command, receipt.receipt))
    assert snapshot.revision.origin == origin
    assert snapshot.revision.operation_id == command.operation_id
    assert snapshot.revision.producer_id.endswith(str(command.principal.api_key_id))
    with pytest.raises(ArtifactError) as failure:
        await api.write_text(replace(command, origin='application'))
    assert failure.value.code == 'ARTIFACT_IDEMPOTENCY_CONFLICT'
