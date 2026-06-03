from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.core.domain.errors import ProjectNotFoundError
from modules.core.domain.repositories import (
    ApiKeyRepository,
    ProjectRepository,
)
from modules.core.infra.repositories import (
    SQLAlchemyApiKeyRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyProjectRepository,
)
from modules.core.service.dtos import (
    CreateApiKeyOutput,
    CreateProjectOutput,
)
from modules.core.service.use_cases import (
    CreateApiKeyUseCase,
    CreateProjectUseCase,
)


def get_create_project_use_case(session: AsyncSession) -> CreateProjectUseCase:
    return CreateProjectUseCase(
        project_repo=SQLAlchemyProjectRepository(session),
        outbox=SQLAlchemyOutboxEventWriter(session),
    )


def get_create_api_key_use_case(session: AsyncSession) -> CreateApiKeyUseCase:
    return CreateApiKeyUseCase(
        project_repo=SQLAlchemyProjectRepository(session),
        api_key_repo=SQLAlchemyApiKeyRepository(session),
        outbox=SQLAlchemyOutboxEventWriter(session),
    )


class GetProjectByIdUseCase:
    def __init__(self, project_repo: ProjectRepository) -> None:
        self._project_repo = project_repo

    async def execute(self, project_id: UUID) -> CreateProjectOutput:
        project = await self._project_repo.get_by_id(project_id)
        if not project:
            raise ProjectNotFoundError(project_id)
        return CreateProjectOutput(
            id=project.id,
            organization_id=project.organization_id,
            name=project.name,
            slug=project.slug,
            status=project.status,
            created_at=project.created_at,
        )


def get_project_by_id_use_case(
    session: AsyncSession,
) -> GetProjectByIdUseCase:
    return GetProjectByIdUseCase(
        project_repo=SQLAlchemyProjectRepository(session),
    )


class ListApiKeysByProjectUseCase:
    def __init__(self, api_key_repo: ApiKeyRepository) -> None:
        self._api_key_repo = api_key_repo

    async def execute(self, project_id: UUID) -> list[CreateApiKeyOutput]:
        keys = await self._api_key_repo.list_by_project(project_id)
        return [
            CreateApiKeyOutput(
                id=k.id,
                project_id=k.project_id,
                name=k.name,
                key_prefix=k.key_prefix,
                key_hash=k.key_hash,
                status=k.status,
                created_at=k.created_at,
            )
            for k in keys
        ]


def list_api_keys_by_project_use_case(
    session: AsyncSession,
) -> ListApiKeysByProjectUseCase:
    return ListApiKeysByProjectUseCase(
        api_key_repo=SQLAlchemyApiKeyRepository(session),
    )
