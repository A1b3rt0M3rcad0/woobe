from modules.core.application.dtos.create_project_dtos import (
    CreateProjectInput,
    CreateProjectOutput,
)
from modules.core.application.interfaces.outbox import OutboxEventWriter
from modules.core.application.interfaces.project_access import ProjectAccessRepository
from modules.core.application.interfaces.repositories import ProjectRepository
from modules.core.domain.entities import Project
from modules.core.domain.errors import DuplicateSlugError


class CreateProjectUseCase:
    def __init__(
        self,
        project_repo: ProjectRepository,
        outbox: OutboxEventWriter,
        access_repo: ProjectAccessRepository | None = None,
    ) -> None:
        self._project_repo = project_repo
        self._outbox = outbox
        self._access_repo = access_repo

    async def execute(self, input_dto: CreateProjectInput) -> CreateProjectOutput:
        if self._access_repo is not None and input_dto.actor_user_id is not None:
            await self._access_repo.require_workspace_admin(
                input_dto.actor_user_id,
                input_dto.workspace_id,
            )

        existing = await self._project_repo.get_by_workspace_and_slug(
            input_dto.workspace_id,
            input_dto.slug,
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

        if self._access_repo is not None and input_dto.actor_user_id is not None:
            await self._access_repo.ensure_creator_access(
                actor_user_id=input_dto.actor_user_id,
                project_id=saved.id,
            )

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
