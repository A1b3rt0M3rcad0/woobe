from typing import Protocol

from modules.artifacts.domain.models import Scope, Workspace, WorkspaceGrant


class WorkspaceStore(Protocol):
    async def provision_workspace(self, workspace: Workspace, fingerprint: str) -> tuple[Workspace, bool]: ...

    async def resolve_workspace(self, scope: Scope, namespace: str, key: str) -> Workspace: ...

    async def accessible_workspaces(self, scope: Scope, principal_id: str, *, limit: int,
                                     after_id: str | None = None,
                                     namespace: str | None = None) -> tuple[Workspace, ...]: ...

    async def update_workspace(self, scope: Scope, workspace_id: str, *, expected_version: int,
                               name: str | None = None, status: str | None = None,
                               labels: dict[str, str] | None = None) -> Workspace: ...


class GrantWriter(Protocol):
    async def add(self, grant: WorkspaceGrant) -> None: ...

    async def revoke(self, scope: Scope, grant_id: str) -> None: ...
