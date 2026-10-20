from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select

from modules.artifacts.domain.models import Action, Scope, WorkspaceGrant
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.models import GrantModel
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.contracts.errors import AuthorizationError
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal, ProjectApiPrincipal
from shared.security.tenancy import TenantAuthorizer


class ExistingPrincipalAuthority:
    def __init__(self, uow: ArtifactsUnitOfWork):
        self._uow = uow

    async def require(self, principal, scope: Scope, action: Action):
        authority = TenantAuthorizer(self._uow.session)
        context = {'environment': scope.environment.value}
        path = {'project_id': scope.project_id}
        permission = f'artifacts:{action.value}'
        if isinstance(principal, AuthenticatedPrincipal):
            await authority.require_active_human(principal)
            await authority.authorize(user_id=principal.user_id, path_params=path,
                                      query_params={}, body=context,
                                      required_permission=permission,
                                      mutation=action not in {Action.READ, Action.SEARCH})
        elif isinstance(principal, ControlPlanePrincipal):
            await authority.require_active_control(principal)
            await authority.authorize_control_key(
                api_key_id=principal.api_key_id, workspace_id=principal.workspace_id,
                workspace_permissions=principal.permissions, required_permission=permission,
                path_params=path, query_params={}, body=context)
        elif isinstance(principal, ProjectApiPrincipal) and principal.kind == 'runtime':
            await authority.require_active_runtime(principal, interface='artifacts')
        else:
            raise AuthorizationError('Artifact credential kind is not allowed')


class GrantRepository:
    def __init__(self, uow: ArtifactsUnitOfWork):
        self._uow = uow
        self._catalog = CatalogRepository(uow)

    async def workspace(self, scope: Scope, workspace_id: str):
        return await self._catalog.workspace(scope, workspace_id)

    async def current(self, principal_id: str, scope: Scope) -> tuple[WorkspaceGrant, ...]:
        rows = (await self._uow.session.execute(select(GrantModel).where(
            GrantModel.principal_id == principal_id,
            GrantModel.project_id == UUID(scope.project_id),
            GrantModel.environment == scope.environment.value,
            GrantModel.revoked.is_(False),
            or_(GrantModel.expires_at.is_(None), GrantModel.expires_at > datetime.now(UTC)),
        ).with_for_update(read=True).execution_options(populate_existing=True))).scalars()
        return tuple(WorkspaceGrant(
            id=row.id, principal_id=row.principal_id, scope=scope,
            actions=frozenset(Action(action) for action in row.actions),
            workspace_id=row.workspace_id, external_namespace=row.external_namespace,
            revision=row.revision, expires_at=row.expires_at, revoked=row.revoked,
        ) for row in rows)

    async def add(self, grant: WorkspaceGrant):
        if grant.workspace_id is not None:
            await self._catalog.workspace(grant.scope, grant.workspace_id)
        self._uow.session.add(GrantModel(
            id=grant.id, project_id=UUID(grant.scope.project_id), environment=grant.scope.environment.value,
            principal_id=grant.principal_id, workspace_id=grant.workspace_id,
            external_namespace=grant.external_namespace, actions=sorted(grant.actions),
            revision=grant.revision, expires_at=grant.expires_at, revoked=grant.revoked,
        ))
        await self._uow.session.flush()

    async def revoke(self, scope: Scope, grant_id: str):
        row = (await self._uow.session.execute(select(GrantModel).where(
            GrantModel.id == grant_id, GrantModel.project_id == UUID(scope.project_id),
            GrantModel.environment == scope.environment.value,
        ).with_for_update())).scalar_one_or_none()
        if row is not None and not row.revoked:
            row.revoked = True
            row.revision += 1
            await self._uow.session.flush()
