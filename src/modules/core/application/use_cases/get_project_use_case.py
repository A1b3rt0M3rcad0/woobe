from modules.core.application.dtos.get_project_dtos import GetProjectInput, GetProjectOutput
from modules.core.domain.errors import ProjectNotFoundError
from modules.core.domain.repositories import ProjectRepository


class GetProjectByIdUseCase:
    def __init__(self, project_repo: ProjectRepository) -> None:
        self._project_repo = project_repo

    async def execute(self, input_dto: GetProjectInput) -> GetProjectOutput:
        project = await self._project_repo.get_by_id(input_dto.project_id)
        if project is None:
            raise ProjectNotFoundError(input_dto.project_id)
        return GetProjectOutput(
            id=project.id,
            workspace_id=project.workspace_id,
            name=project.name,
            slug=project.slug,
            status=project.status,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
