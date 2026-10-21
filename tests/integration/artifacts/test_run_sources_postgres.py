from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from modules.artifacts.application.contracts.files import ListFiles, ReadFile
from modules.artifacts.domain.models import ArtifactError, Environment, Locator, Scope, SourceRef, Workspace
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.run_sources import RunSourceRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from tests.integration.artifacts.test_files_postgres import prepare as prepare_files
from tests.integration.artifacts.test_uploads_postgres import object_store as object_store


@pytest.mark.asyncio
async def test_run_source_manifest_is_exact_deduplicated_and_pinned(artifacts_database, engine):
    scope = Scope(str(UUID(artifacts_database['project_id'])), Environment.STAGING)
    workspace = Workspace(
        id='run-source-workspace', scope=scope, external_namespace='source-tests',
        external_key='manifest', name='Manifest', catalog_version=12,
    )
    async with ArtifactsUnitOfWork(engine) as uow:
        await CatalogRepository(uow).insert_workspace(workspace)

    first = SourceRef('artifact-source-a', 'revision-source-a', 'a' * 64,
        representation_set_id='representation-source-a',
        locator=Locator(block_id='block-source-a', char_start=0, char_end=5,
            char_space='canonical_block_text'))
    second = SourceRef('artifact-source-b', 'revision-source-b', 'b' * 64)
    async with ArtifactsUnitOfWork(engine) as uow:
        repository = RunSourceRepository(uow)
        await repository.record(scope, workspace.id, 'run-source-1', 10, first)
        repeated = await repository.record(scope, workspace.id, 'run-source-1', 10, first)
        manifest = await repository.record(scope, workspace.id, 'run-source-1', 10, second)

    assert repeated.sources == (first,)
    assert set(manifest.sources) == {first, second}
    async with ArtifactsUnitOfWork(engine) as uow:
        loaded = await RunSourceRepository(uow).get(scope, workspace.id, 'run-source-1')
    assert loaded == manifest

    async with ArtifactsUnitOfWork(engine) as uow:
        with pytest.raises(ArtifactError) as conflict:
            await RunSourceRepository(uow).record(scope, workspace.id, 'run-source-1', 11,
                SourceRef('artifact-source-c', 'revision-source-c', 'c' * 64))
    assert conflict.value.code == 'ARTIFACT_INVALID_CURSOR'


@pytest.mark.asyncio
async def test_run_source_manifests_are_isolated_per_run(artifacts_database, engine):
    scope = Scope(str(UUID(artifacts_database['project_id'])), Environment.STAGING)
    workspace = Workspace(
        id='run-source-isolation', scope=scope, external_namespace='source-tests',
        external_key='isolated', name='Isolation', catalog_version=3,
    )
    source = SourceRef('artifact-isolated-a', 'revision-isolated-a', 'd' * 64)
    async with ArtifactsUnitOfWork(engine) as uow:
        await CatalogRepository(uow).insert_workspace(workspace)
        repository = RunSourceRepository(uow)
        await repository.record(scope, workspace.id, 'run-one', 3, source)
        await repository.record(scope, workspace.id, 'run-two', 3, source)

    async with ArtifactsUnitOfWork(engine) as uow:
        repository = RunSourceRepository(uow)
        one = await repository.get(scope, workspace.id, 'run-one')
        two = await repository.get(scope, workspace.id, 'run-two')
    assert one == two and one.sources == (source,)


@pytest.mark.asyncio
async def test_pinned_reads_keep_old_revision_and_allow_only_explicit_run_outputs(
    artifacts_database, engine, object_store
):
    api, command = await prepare_files(engine, artifacts_database['project_id'], object_store)
    original = await api.write_text(command)
    async with ArtifactsUnitOfWork(engine) as uow:
        from modules.artifacts.infra.database.catalog import CatalogRepository

        workspace = await CatalogRepository(uow).workspace(command.scope, command.workspace_id)
        accepted_catalog = workspace.catalog_version

    updated = await api.write_text(replace(command, operation_id=str(uuid4()),
        artifact_id=original.receipt.artifact_id, expected_revision=original.receipt.revision_id,
        text='new concurrent revision', origin='agent', run_id='run-pinned-1', node_id='node-pinned-a'))
    historical = ReadFile(command.principal, command.scope, command.workspace_id,
        original.receipt.artifact_id, original.receipt.revision_id,
        catalog_version=accepted_catalog)
    assert (await api.resolve(historical)).revision.id == original.receipt.revision_id

    unseen = ReadFile(command.principal, command.scope, command.workspace_id,
        updated.receipt.artifact_id, updated.receipt.revision_id, catalog_version=accepted_catalog)
    with pytest.raises(ArtifactError) as hidden:
        await api.resolve(unseen)
    assert hidden.value.code == 'SOURCE_UNAVAILABLE'

    overlay = replace(unseen, run_id='run-pinned-1', output_node_ids=frozenset({'node-pinned-a'}))
    assert (await api.resolve(overlay)).revision.id == updated.receipt.revision_id
    with pytest.raises(ArtifactError):
        await api.resolve(replace(overlay, output_node_ids=frozenset({'node-pinned-b'})))

    old_page = await api.list(ListFiles(command.principal, command.scope, command.workspace_id,
        directory='docs', catalog_version=accepted_catalog))
    assert any(item.id == original.receipt.artifact_id and item.revision_id == original.receipt.revision_id
        for item in old_page.items), (accepted_catalog, old_page.items, original, updated)
