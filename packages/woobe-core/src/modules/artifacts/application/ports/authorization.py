from typing import Protocol

from modules.artifacts.domain.models import Action, Scope, Workspace, WorkspaceGrant
from shared.security.principal import SecurityPrincipal


class PrincipalAuthority(Protocol):
    async def require(self, principal: SecurityPrincipal, scope: Scope, action: Action) -> None: ...


class GrantReader(Protocol):
    async def current(self, principal_id: str, scope: Scope) -> tuple[WorkspaceGrant, ...]: ...

    async def workspace(self, scope: Scope, workspace_id: str) -> Workspace: ...
