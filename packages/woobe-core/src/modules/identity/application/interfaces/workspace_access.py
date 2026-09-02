from typing import Protocol
from uuid import UUID


class WorkspaceAccessRepository(Protocol):
    async def require_member(self, user_id: UUID, workspace_id: UUID) -> str: ...

    async def require_admin(self, user_id: UUID, workspace_id: UUID) -> str: ...

    async def require_role_assignment(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        target_role: str,
    ) -> str: ...

    async def require_valid_invite_acceptance(
        self,
        *,
        user_id: UUID,
        invite_id: UUID,
    ) -> None: ...

    async def list_members(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
    ) -> list[dict[str, object]]: ...

    async def remove_member(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        target_user_id: UUID,
    ) -> dict[str, object]: ...

    async def list_invites(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
    ) -> list[dict[str, object]]: ...

    async def cancel_invite(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        invite_id: UUID,
    ) -> dict[str, object]: ...
