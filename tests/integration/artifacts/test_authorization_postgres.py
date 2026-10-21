from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from modules.artifacts.application.authorization import ArtifactAuthorization, principal_identity
from modules.artifacts.domain.models import Action, ArtifactError, Scope, Workspace, WorkspaceGrant
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.security.principal import ProjectApiPrincipal


async def prepare(engine, project):
    kid, target = uuid4(), uuid4()
    actor = ProjectApiPrincipal(api_key_id=kid, project_id=UUID(project),
        key_prefix='fixture', kind='runtime', target_type='agent', target_id=target,
        environment='staging', interfaces=frozenset({'artifacts'}),
        scopes=frozenset({'runtime:execute'}), authenticated_at=datetime.now(UTC))
    workspace = Workspace(str(uuid4()), Scope(project, 'staging'), 'app', str(uuid4()), 'Files')
    grant = WorkspaceGrant(str(uuid4()), principal_identity(actor), workspace.scope,
                            frozenset({Action.READ}), workspace_id=workspace.id)
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text("""INSERT INTO core.api_keys
            (id,credential_id,project_id,name,key_prefix,key_hash,key_version,scopes,kind,
             agent_id,target_type,target_id,environment,interfaces,status)
            VALUES (:id,:id,:project,'Artifact authority fixture','fixture',:digest,1,
                    '["runtime:execute"]','runtime',:target,'agent',:target,'staging',
                    '["artifacts"]','active')"""),
            {'id': kid, 'project': UUID(project), 'target': target,
             'digest': uuid4().bytes + uuid4().bytes})
        await CatalogRepository(uow).insert_workspace(workspace)
        await GrantRepository(uow).add(grant)
    return actor, workspace, grant


async def require(engine, actor, workspace, action=Action.READ):
    async with ArtifactsUnitOfWork(engine) as uow:
        return await ArtifactAuthorization(ExistingPrincipalAuthority(uow), GrantRepository(uow)).authorize(
            actor, workspace.scope, workspace.id, action)


async def test_persisted_grant_revocation_is_effective_after_admission(engine, artifacts_database):
    actor, workspace, grant = await prepare(engine, artifacts_database['project_id'])
    assert await require(engine, actor, workspace) == workspace
    async with ArtifactsUnitOfWork(engine) as uow:
        await GrantRepository(uow).revoke(workspace.scope, grant.id)
    with pytest.raises(ArtifactError) as failure:
        await require(engine, actor, workspace)
    assert failure.value.code == 'ARTIFACT_ACCESS_DENIED'


@pytest.mark.parametrize('mutation', ['revoked', 'expired', 'interface', 'environment', 'delegation'])
async def test_current_credential_state_restricts_retained_principal(engine, artifacts_database, mutation):
    actor, workspace, grant = await prepare(engine, artifacts_database['project_id'])
    await require(engine, actor, workspace)
    statements = {
        'revoked': "status='revoked', revoked_at=now()",
        'expired': "expires_at=now()-interval '1 second'",
        'interface': "interfaces='[\"http\"]'::jsonb",
        'environment': "environment='production'",
        'delegation': "delegation_expires_at=now()-interval '1 second'",
    }
    async with ArtifactsUnitOfWork(engine) as uow:
        # SQL fragments come solely from this fixed test matrix, never a request.
        await uow.session.execute(text('UPDATE core.api_keys SET ' + statements[mutation] + ' WHERE id=:id'), {'id': actor.api_key_id})
    with pytest.raises(ArtifactError) as failure:
        await require(engine, actor, workspace)
    assert failure.value.code == 'ARTIFACT_ACCESS_DENIED'


async def test_expired_and_cross_scope_grants_never_authorize(engine, artifacts_database):
    actor, workspace, grant = await prepare(engine, artifacts_database['project_id'])
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text('UPDATE artifacts.grants SET expires_at=:expiry WHERE id=:id'),
                                  {'expiry': datetime.now(UTC)-timedelta(seconds=1), 'id': grant.id})
    with pytest.raises(ArtifactError):
        await require(engine, actor, workspace)
    with pytest.raises(ArtifactError):
        await require(engine, actor.model_copy(update={'project_id': uuid4()}), workspace)
    with pytest.raises(ArtifactError):
        await require(engine, actor, workspace, Action.WRITE)
