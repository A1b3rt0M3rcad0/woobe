from modules.core.domain.entities import Project
from modules.core.domain.errors import DuplicateSlugError
from modules.core.domain.repositories import ProjectRepository
from modules.core.application.dtos.create_project_dtos import CreateProjectInput, CreateProjectOutput
from shared.messaging.outbox_writer import OutboxEventWriter


class CreateProjectUseCase:

    def __init__(
        self,
        project_repo: ProjectRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._project_repo = project_repo
        self._outbox = outbox

    async def execute(self, input_dto: CreateProjectInput) -> CreateProjectOutput:
        existing = await self._project_repo.get_by_workspace_and_slug(
            input_dto.workspace_id, input_dto.slug
        )
        if existing:
            raise DuplicateSlugError(
                f"Project with slug '{input_dto.slug}' already exists in this workspace"
            )

        project = Project(
            workspace_id=input_dto.workspace_id,
            name=input_dto.name,
            slug=input_dto.slug,
        )
        saved = await self._project_repo.save(project)

        await self._outbox.write(
            aggregate_type="project",
            aggregate_id=saved.id,
            event_type="project.created.v1",
            payload={
                "workspace_id": str(saved.workspace_id),
                "name": saved.name,
                "slug": saved.slug,
            },
            routing_key="project.created.v1",
            idempotency_key=f"core:project.created.v1:{saved.id}",
        )

        return CreateProjectOutput(
            id=saved.id,
            workspace_id=saved.workspace_id,
            name=saved.name,
            slug=saved.slug,
            status=saved.status,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )
