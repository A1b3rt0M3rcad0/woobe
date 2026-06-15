from modules.core.domain.repositories import ProjectRepository
from modules.core.application.dtos.list_projects_dtos import ListProjectsInput, ListProjectsOutput


class ListProjectsUseCase:

    def __init__(self, project_repo: ProjectRepository) -> None:
        self._project_repo = project_repo

    async def execute(self, input_dto: ListProjectsInput) -> list[ListProjectsOutput]:
        if input_dto.organization_id:
            projects = await self._project_repo.list_by_organization(input_dto.organization_id)
        else:
            projects = []
        return [ListProjectsOutput(
            id=p.id,
            organization_id=p.organization_id,
            name=p.name,
            slug=p.slug,
            status=p.status,
            created_at=p.created_at,
            updated_at=p.updated_at,
        ) for p in projects]
