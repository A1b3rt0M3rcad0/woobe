from datetime import UTC, datetime

from modules.core.domain.errors import ProjectNotFoundError
from modules.core.domain.repositories import ProjectRepository
from modules.core.application.dtos.update_project_dtos import UpdateProjectInput, UpdateProjectOutput
from shared.domain.events import OutboxEventWriter


class UpdateProjectUseCase:

    def __init__(self, project_repo: ProjectRepository, outbox: OutboxEventWriter) -> None:
        self._project_repo = project_repo
        self._outbox = outbox

    async def execute(self, input_dto: UpdateProjectInput) -> UpdateProjectOutput:
        project = await self._project_repo.get_by_id(input_dto.project_id)
        if not project:
            raise ProjectNotFoundError(input_dto.project_id)

        if input_dto.name is not None:
            project.name = input_dto.name
        if input_dto.slug is not None:
            project.slug = input_dto.slug

        project.updated_at = datetime.now(UTC)
        saved = await self._project_repo.save(project)

        await self._outbox.write(
            aggregate_type="project",
            aggregate_id=saved.id,
            event_type="project.updated",
            payload={"name": saved.name, "slug": saved.slug},
        )

        return UpdateProjectOutput(
            id=saved.id,
            organization_id=saved.organization_id,
            name=saved.name,
            slug=saved.slug,
            status=saved.status,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )
