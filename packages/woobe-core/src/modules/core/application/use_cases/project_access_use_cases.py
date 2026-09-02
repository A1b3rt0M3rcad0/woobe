from uuid import UUID

from modules.core.application.interfaces.project_access import ProjectAccessRepository


class ListAccessibleProjectsUseCase:
    def __init__(self, repository: ProjectAccessRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> list[dict[str, object]]:
        return await self._repository.list_accessible_projects(
            user_id=user_id,
            workspace_id=workspace_id,
        )


class ListProjectsForAccessManagementUseCase:
    def __init__(self, repository: ProjectAccessRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> list[dict[str, object]]:
        return await self._repository.list_projects_for_access_management(
            user_id=user_id,
            workspace_id=workspace_id,
        )


class ListProjectMembersUseCase:
    def __init__(self, repository: ProjectAccessRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
    ) -> dict[str, object]:
        return await self._repository.list_project_members(
            user_id=user_id,
            project_id=project_id,
        )


class GrantProjectSubjectAccessUseCase:
    def __init__(self, repository: ProjectAccessRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
        subject_type: str,
        subject_id: UUID,
    ) -> dict[str, object]:
        return await self._repository.grant_project_subject_access(
            actor_user_id=actor_user_id,
            project_id=project_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )


class RevokeProjectSubjectAccessUseCase:
    def __init__(self, repository: ProjectAccessRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
        subject_type: str,
        subject_id: UUID,
    ) -> None:
        await self._repository.revoke_project_subject_access(
            actor_user_id=actor_user_id,
            project_id=project_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )


class GrantProjectAccessUseCase:
    def __init__(self, repository: ProjectAccessRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
        email: str,
    ) -> dict[str, object]:
        return await self._repository.grant_project_access(
            actor_user_id=actor_user_id,
            project_id=project_id,
            email=email,
        )


class RevokeProjectAccessUseCase:
    def __init__(self, repository: ProjectAccessRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
        target_user_id: UUID,
    ) -> None:
        await self._repository.revoke_project_access(
            actor_user_id=actor_user_id,
            project_id=project_id,
            target_user_id=target_user_id,
        )
