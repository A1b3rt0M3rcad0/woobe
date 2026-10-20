from datetime import UTC, datetime

from modules.artifacts.application.ports.authorization import GrantReader, PrincipalAuthority
from modules.artifacts.domain.models import Action, ArtifactError, Scope, Workspace, WorkspaceGrant
from shared.contracts.errors import AuthenticationError, AuthorizationError, NotFoundError
from shared.security.principal import (
    AuthenticatedPrincipal, ControlPlanePrincipal, ProjectApiPrincipal, SecurityPrincipal,
)


def principal_identity(principal: SecurityPrincipal) -> str:
    if isinstance(principal, AuthenticatedPrincipal):
        return f'user-{principal.user_id}'
    if isinstance(principal, ControlPlanePrincipal):
        return f'control-{principal.api_key_id}'
    if isinstance(principal, ProjectApiPrincipal) and principal.kind == 'runtime':
        return f'runtime-{principal.api_key_id}'
    raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Artifact access is denied')


class ArtifactAuthorization:
    """One operation decision for direct access, runtime, workers and transfers.

    Call again in each operation's short transaction. Neither a binding nor a
    previously returned grant is retained as irrevocable authorization.
    """

    def __init__(self, authority: PrincipalAuthority, reader: GrantReader):
        self._authority = authority
        self._reader = reader

    async def require_project(self, principal: SecurityPrincipal, scope: Scope, action: Action):
        try:
            principal_identity(principal)
            if isinstance(principal, ProjectApiPrincipal):
                if (str(principal.project_id) != scope.project_id
                        or principal.environment != scope.environment.value
                        or not principal.allows_interface('artifacts')):
                    raise AuthorizationError('Insufficient runtime scope')
            await self._authority.require(principal, scope, action)
        except (AuthenticationError, AuthorizationError, NotFoundError, ArtifactError) as error:
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Artifact access is denied') from error

    @staticmethod
    def _allows(grant: WorkspaceGrant, scope: Scope, action: Action, *,
                workspace: Workspace | None = None, namespace: str | None = None):
        if grant.scope != scope or grant.revoked or action not in grant.actions:
            return False
        if grant.expires_at is not None and grant.expires_at <= datetime.now(UTC):
            return False
        if workspace is not None:
            return grant.workspace_id == workspace.id or (
                grant.external_namespace is not None
                and grant.external_namespace == workspace.external_namespace)
        return grant.external_namespace is not None and grant.external_namespace == namespace

    async def authorize(self, principal: SecurityPrincipal, scope: Scope, workspace_id: str,
                        action: Action, *, release_actions: frozenset[Action] | None = None,
                        node_actions: frozenset[Action] | None = None,
                        workspace_limit: str | None = None) -> Workspace:
        await self.require_project(principal, scope, action)
        if ((release_actions is not None and action not in release_actions)
                or (node_actions is not None and action not in node_actions)
                or (workspace_limit is not None and workspace_id != workspace_limit)):
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Artifact access is denied')
        try:
            workspace = await self._reader.workspace(scope, workspace_id)
        except ArtifactError as error:
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Artifact access is denied') from error
        if (workspace.status not in {'active', 'archived'}
            and not (workspace.status == 'deletion_pending' and action == Action.MANAGE)) or (
            workspace.status == 'archived' and action not in {Action.READ, Action.SEARCH, Action.MANAGE}
        ):
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Artifact access is denied')
        grants = await self._reader.current(principal_identity(principal), scope)
        if not any(self._allows(grant, scope, action, workspace=workspace) for grant in grants):
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Artifact access is denied')
        return workspace

    async def authorize_namespace(self, principal: SecurityPrincipal, scope: Scope,
                                  namespace: str, action: Action):
        await self.require_project(principal, scope, action)
        # Administrative creation/grant management is already project-authorized.
        # Runtime credentials additionally require an explicit namespace grant.
        if isinstance(principal, ProjectApiPrincipal):
            grants = await self._reader.current(principal_identity(principal), scope)
            if not any(self._allows(grant, scope, action, namespace=namespace) for grant in grants):
                raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Artifact access is denied')
