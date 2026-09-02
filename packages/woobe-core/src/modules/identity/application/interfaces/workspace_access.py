from typing import Protocol
from uuid import UUID


class WorkspaceAccessRepository(Protocol):
    async def require_admin(self, user_id: UUID, workspace_id: UUID) -> str: ...

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
