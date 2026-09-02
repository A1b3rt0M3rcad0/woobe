from typing import Protocol
from uuid import UUID


class ProjectAccessRepository(Protocol):
    async def require_workspace_admin(
        self,
        user_id: UUID,
        workspace_id: UUID,
    ) -> str: ...

    async def list_accessible_projects(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> list[dict[str, object]]: ...

    async def list_projects_for_access_management(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> list[dict[str, object]]: ...

    async def list_project_members(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
    ) -> dict[str, object]: ...

    async def grant_project_subject_access(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
        subject_type: str,
        subject_id: UUID,
    ) -> dict[str, object]: ...

    async def revoke_project_subject_access(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
        subject_type: str,
        subject_id: UUID,
    ) -> None: ...

    async def grant_project_access(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
        email: str,
    ) -> dict[str, object]: ...

    async def revoke_project_access(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
        target_user_id: UUID,
    ) -> None: ...

    async def ensure_creator_access(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
    ) -> None: ...
