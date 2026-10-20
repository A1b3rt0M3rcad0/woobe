import asyncio
from uuid import uuid4

import psycopg2
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from modules.artifacts.domain.models import ArtifactError, ArtifactRef, Revision, Scope, Workspace
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.models import RevisionModel
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork


def revision(artifact_id=None):
    aid = artifact_id or str(uuid4())
    rid = str(uuid4())
    return Revision(rid, aid, f'projects/p/draft/workspaces/w/{aid}/{rid}',
                    'text/plain', 12, 'a' * 64, 'application')


@pytest.fixture
async def engine(artifacts_database):
    engine = create_async_engine(artifacts_database['url'])
    try:
        yield engine
    finally:
        await engine.dispose()


async def create_workspace(engine, project_id):
    ws = Workspace(str(uuid4()), Scope(project_id, 'draft'), 'consumer', str(uuid4()), 'Docs')
    async with ArtifactsUnitOfWork(engine) as uow:
        await CatalogRepository(uow).insert_workspace(ws)
    return ws


def test_baseline_data_survives_additive_migration_and_ledger_is_current(artifacts_database):
    with psycopg2.connect(artifacts_database['sync_url']) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT name FROM core.projects WHERE id=%s', (artifacts_database['project_id'],))
            assert cursor.fetchone()[0] == 'Baseline retained'
            cursor.execute('SELECT version_num FROM alembic_version')
            assert cursor.fetchone()[0] == '0107'


async def test_catalog_visibility_and_immutable_revision_history(engine, artifacts_database):
    ws = await create_workspace(engine, artifacts_database['project_id'])
    first = revision()
    async with ArtifactsUnitOfWork(engine) as uow:
        await CatalogRepository(uow).publish_revision(ws.scope, ws.id, path='doc.txt', revision=first, expected_revision=None)
    second = revision(first.artifact_id)
    async with ArtifactsUnitOfWork(engine) as uow:
        await CatalogRepository(uow).publish_revision(ws.scope, ws.id, path='doc.txt', revision=second, expected_revision=first.id)
    async with ArtifactsUnitOfWork(engine) as uow:
        repo = CatalogRepository(uow)
        assert (await repo.workspace(ws.scope, ws.id)).catalog_version == 2
        assert (await repo.visible_artifacts(ws.scope, ws.id, catalog_version=1))[0].revision_id == first.id
        assert (await repo.visible_artifacts(ws.scope, ws.id, catalog_version=2))[0].revision_id == second.id
        assert await repo.visible_artifacts(ws.scope, ws.id, catalog_version=0) == ()
        assert (await repo.revision(ws.scope, ws.id, ArtifactRef(first.artifact_id, first.id))).sha256 == first.sha256
    with pytest.raises(DBAPIError, match='immutable'):
        async with ArtifactsUnitOfWork(engine) as uow:
            await uow.session.execute(text('UPDATE artifacts.revisions SET size_bytes=13 WHERE id=:id'), {'id': first.id})


async def test_transaction_rollback_reverts_revision_head_and_accounting(engine, artifacts_database):
    ws = await create_workspace(engine, artifacts_database['project_id'])
    first = revision()
    with pytest.raises(RuntimeError, match='crash'):
        async with ArtifactsUnitOfWork(engine) as uow:
            await CatalogRepository(uow).publish_revision(ws.scope, ws.id, path='doc.txt', revision=first, expected_revision=None)
            raise RuntimeError('crash before commit')
    async with ArtifactsUnitOfWork(engine) as uow:
        repo = CatalogRepository(uow)
        state = await repo.workspace(ws.scope, ws.id)
        assert state.catalog_version == state.used_bytes == 0
        assert (await uow.session.execute(select(RevisionModel).where(RevisionModel.id == first.id))).scalar_one_or_none() is None


async def test_concurrent_compare_and_swap_has_one_winner(engine, artifacts_database):
    ws = await create_workspace(engine, artifacts_database['project_id'])
    first = revision()
    async with ArtifactsUnitOfWork(engine) as uow:
        await CatalogRepository(uow).publish_revision(ws.scope, ws.id, path='doc.txt', revision=first, expected_revision=None)

    async def replace():
        try:
            async with ArtifactsUnitOfWork(engine) as uow:
                result = await CatalogRepository(uow).publish_revision(ws.scope, ws.id, path='doc.txt', revision=revision(first.artifact_id), expected_revision=first.id)
            return result
        except ArtifactError as error:
            return error.code

    results = await asyncio.gather(replace(), replace())
    assert sum(result == 'ARTIFACT_REVISION_CONFLICT' for result in results) == 1
    async with ArtifactsUnitOfWork(engine) as uow:
        state = await CatalogRepository(uow).workspace(ws.scope, ws.id)
        assert state.catalog_version == 2 and state.used_bytes == 24


async def test_scope_filters_uniqueness_and_indexed_lookup(engine, artifacts_database):
    ws = await create_workspace(engine, artifacts_database['project_id'])
    async with ArtifactsUnitOfWork(engine) as uow:
        repo = CatalogRepository(uow)
        for scope in (Scope(str(uuid4()), 'draft'), Scope(ws.scope.project_id, 'production')):
            assert await repo.list_workspaces(scope) == ()
            with pytest.raises(ArtifactError, match='unavailable'):
                await repo.workspace(scope, ws.id)
        await uow.session.execute(text('SET LOCAL enable_seqscan = off'))
        plan = (await uow.session.execute(text('EXPLAIN SELECT id FROM artifacts.workspaces WHERE project_id=:project AND environment=\'draft\' ORDER BY id LIMIT 10'), {'project': ws.scope.project_id})).scalars().all()
        assert any('Index' in line for line in plan)
    duplicate = Workspace(str(uuid4()), ws.scope, ws.external_namespace, ws.external_key, 'Duplicate')
    with pytest.raises(IntegrityError):
        async with ArtifactsUnitOfWork(engine) as uow:
            await CatalogRepository(uow).insert_workspace(duplicate)


async def test_live_paths_and_revision_ownership_are_enforced_by_postgres(engine, artifacts_database):
    ws = await create_workspace(engine, artifacts_database['project_id'])
    first, second = revision(), revision()
    async with ArtifactsUnitOfWork(engine) as uow:
        repo = CatalogRepository(uow)
        await repo.publish_revision(ws.scope, ws.id, path='first.txt', revision=first, expected_revision=None)
        await repo.publish_revision(ws.scope, ws.id, path='second.txt', revision=second, expected_revision=None)
    with pytest.raises(IntegrityError):
        async with ArtifactsUnitOfWork(engine) as uow:
            await CatalogRepository(uow).publish_revision(ws.scope, ws.id, path='first.txt', revision=revision(), expected_revision=None)
    with pytest.raises(IntegrityError):
        async with ArtifactsUnitOfWork(engine) as uow:
            await uow.session.execute(text('UPDATE artifacts.artifacts SET revision_id=:revision WHERE id=:artifact'),
                                      {'revision': second.id, 'artifact': first.artifact_id})
    async with ArtifactsUnitOfWork(engine) as uow:
        repo = CatalogRepository(uow)
        assert (await repo.artifact_row(ws.scope, ws.id, first.artifact_id)).revision_id == first.id
        for scope in (Scope(str(uuid4()), 'draft'), Scope(ws.scope.project_id, 'production')):
            with pytest.raises(ArtifactError) as failure:
                await repo.revision(scope, ws.id, ArtifactRef(first.artifact_id, first.id))
            assert failure.value.code == 'SOURCE_UNAVAILABLE'


async def test_logical_deletion_hides_historical_heads(engine, artifacts_database):
    ws = await create_workspace(engine, artifacts_database['project_id'])
    first = revision()
    async with ArtifactsUnitOfWork(engine) as uow:
        await CatalogRepository(uow).publish_revision(ws.scope, ws.id, path='deleted.txt', revision=first, expected_revision=None)
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text('UPDATE artifacts.artifacts SET deleted=true WHERE id=:id'), {'id': first.artifact_id})
    async with ArtifactsUnitOfWork(engine) as uow:
        repo = CatalogRepository(uow)
        assert await repo.visible_artifacts(ws.scope, ws.id, catalog_version=1) == ()
        with pytest.raises(ArtifactError):
            await repo.revision(ws.scope, ws.id, ArtifactRef(first.artifact_id, first.id))
