from datetime import UTC, datetime

from modules.core.domain.errors import ProjectNotFoundError
from modules.core.domain.repositories import ProjectRepository
from modules.core.application.dtos.update_project_dtos import UpdateProjectInput, UpdateProjectOutput
from shared.messaging.outbox_writer import OutboxEventWriter


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
            event_type="project.updated.v1",
            payload={"name": saved.name, "slug": saved.slug},
            routing_key="project.updated.v1",
            idempotency_key=f"core:project.updated.v1:{saved.id}",
        )

        return UpdateProjectOutput(
            id=saved.id,
            workspace_id=saved.workspace_id,
            name=saved.name,
            slug=saved.slug,
            status=saved.status,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )
