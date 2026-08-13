from modules.core.application.dtos.list_projects_dtos import ListProjectsInput, ListProjectsOutput
from modules.core.domain.repositories import ProjectRepository


class ListProjectsUseCase:
    def __init__(self, project_repo: ProjectRepository) -> None:
        self._project_repo = project_repo

    async def execute(self, input_dto: ListProjectsInput) -> list[ListProjectsOutput]:
        projects = (
            await self._project_repo.list_by_workspace(input_dto.workspace_id)
            if input_dto.workspace_id is not None
            else []
        )
        return [
            ListProjectsOutput(
                id=project.id,
                workspace_id=project.workspace_id,
                name=project.name,
                slug=project.slug,
                status=project.status,
                created_at=project.created_at,
                updated_at=project.updated_at,
            )
            for project in projects
        ]
