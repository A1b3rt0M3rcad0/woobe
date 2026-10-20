import asyncio
from dataclasses import replace
import importlib
from uuid import uuid4

import pytest

from modules.artifacts.application.authorization import ArtifactAuthorization, principal_identity
from modules.artifacts.application.contracts.api import WorkspaceCreate, WorkspaceUpdate
from modules.artifacts.application.contracts.workspaces import (
    ChangeWorkspace, CreateWorkspace, ListWorkspaces, ReadWorkspace, ResolveWorkspace,
)
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.application.use_cases.workspaces import WorkspaceUseCases
from modules.artifacts.domain.models import Action, ArtifactError, Scope, WorkspaceGrant
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from tests.integration.artifacts.test_authorization_postgres import prepare


async def prepare_namespace(engine, project):
    actor, unused_workspace, grant = await prepare(engine, project)
    namespace = uuid4().hex
    async with ArtifactsUnitOfWork(engine) as uow:
        await GrantRepository(uow).add(WorkspaceGrant(str(uuid4()), principal_identity(actor),
            unused_workspace.scope, frozenset(Action), external_namespace=namespace))
    definition = WorkspaceCreate(environment='staging', external_namespace=namespace,
                                  external_key=uuid4().hex, name='Documents', labels={'title': 'Friendly'})
    return actor, unused_workspace.scope, definition


async def execute(engine, method, request):
    async with ArtifactsUnitOfWork(engine) as uow:
        grants = GrantRepository(uow)
        service = WorkspaceUseCases(CatalogRepository(uow), grants,
            ArtifactAuthorization(ExistingPrincipalAuthority(uow), grants), CursorCodec(b'f' * 32))
        return await getattr(service, method)(request)


async def test_creation_is_idempotent_under_concurrency_and_payload_changes_conflict(engine, artifacts_database):
    actor, scope, definition = await prepare_namespace(engine, artifacts_database['project_id'])
    request = CreateWorkspace(actor, scope, definition)
    first, second = await asyncio.gather(execute(engine, 'create', request), execute(engine, 'create', request))
    assert first.id == second.id and first.labels == (('title', 'Friendly'),)
    changed = definition.model_copy(update={'quota_bytes': definition.quota_bytes + 1})
    with pytest.raises(ArtifactError) as failure:
        await execute(engine, 'create', replace(request, definition=changed))
    assert failure.value.code == 'ARTIFACT_IDEMPOTENCY_CONFLICT'
    resolved = await execute(engine, 'resolve', ResolveWorkspace(actor, scope,
        definition.external_namespace, definition.external_key))
    assert resolved.id == first.id


async def test_metadata_cas_does_not_change_external_identity_or_storage_receipt(engine, artifacts_database):
    actor, scope, definition = await prepare_namespace(engine, artifacts_database['project_id'])
    request = CreateWorkspace(actor, scope, definition)
    ws = await execute(engine, 'create', request)
    command = ChangeWorkspace(actor, scope, ws.id, WorkspaceUpdate(expected_version=1, name='Renamed'))
    changed = await execute(engine, 'update', command)
    assert changed.version == 2 and changed.storage_profile == ws.storage_profile
    replay = await execute(engine, 'create', request)
    assert replay.id == ws.id and replay.name == 'Renamed'
    with pytest.raises(ArtifactError) as failure:
        await execute(engine, 'update', command)
    assert failure.value.code == 'WORKSPACE_REVISION_CONFLICT'
    pending = await execute(engine, 'update', ChangeWorkspace(actor, scope, ws.id,
        WorkspaceUpdate(expected_version=2, status='deletion_pending')))
    assert pending.status == 'deletion_pending'
    with pytest.raises(ArtifactError):
        await execute(engine, 'get', ReadWorkspace(actor, scope, ws.id))
    with pytest.raises(ArtifactError):
        await execute(engine, 'update', ChangeWorkspace(actor, scope, ws.id,
            WorkspaceUpdate(expected_version=3, status='active')))


async def test_pages_filter_in_sql_and_cursors_cannot_cross_principals_filters_or_environments(engine, artifacts_database):
    actor, scope, definition = await prepare_namespace(engine, artifacts_database['project_id'])
    ids = set()
    for index in range(3):
        ws = await execute(engine, 'create', CreateWorkspace(actor, scope,
            definition.model_copy(update={'external_key': f'item-{index}'})))
        ids.add(ws.id)
    request = ListWorkspaces(actor, scope, limit=1, external_namespace=definition.external_namespace)
    found = set()
    page = await execute(engine, 'list', request)
    assert page.has_more
    first_cursor = page.next_cursor
    while True:
        found.update(item.id for item in page.items)
        if not page.has_more:
            break
        page = await execute(engine, 'list', replace(request, cursor=page.next_cursor))
    assert found == ids
    other, other_scope, other_definition = await prepare_namespace(engine, artifacts_database['project_id'])
    for invalid in (
        replace(request, cursor=first_cursor, principal=other),
        replace(request, cursor=first_cursor, external_namespace='different'),
        replace(request, cursor=first_cursor + 'tampered'),
    ):
        with pytest.raises(ArtifactError) as failure:
            await execute(engine, 'list', invalid)
        assert failure.value.code == 'ARTIFACT_INVALID_CURSOR'
    with pytest.raises(ArtifactError):
        await execute(engine, 'get', ReadWorkspace(actor, Scope(scope.project_id, 'production'), next(iter(ids))))
    assert not (await execute(engine, 'list', ListWorkspaces(other, other_scope))).items or all(
        item.id not in ids for item in (await execute(engine, 'list', ListWorkspaces(other, other_scope))).items)


async def test_creation_fingerprint_is_stable_for_label_order_and_public_composer_works(engine, artifacts_database, monkeypatch):
    actor, scope, definition = await prepare_namespace(engine, artifacts_database['project_id'])
    first = definition.model_copy(update={'labels': {'a': 'A', 'b': 'B'}})
    second = definition.model_copy(update={'labels': {'b': 'B', 'a': 'A'}})
    created = await execute(engine, 'create', CreateWorkspace(actor, scope, first))
    replay = await execute(engine, 'create', CreateWorkspace(actor, scope, second))
    assert replay.id == created.id
    module = importlib.import_module('modules.artifacts.composition.composers.get_workspace')
    monkeypatch.setattr(module, 'DATABASE_ENGINE', engine)
    result = await module.get_workspace_composer()(ReadWorkspace(actor, scope, created.id))
    assert result == replay
