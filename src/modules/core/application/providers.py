from sqlalchemy.ext.asyncio import AsyncSession

from modules.core.domain.repositories import ApiKeyRepository, ProjectRepository
from modules.core.infra.repositories import (
    SQLAlchemyApiKeyRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyProjectRepository,
)
from modules.core.service.use_cases import (
    CreateApiKeyUseCase,
    CreateProjectUseCase,
)
from shared.domain.events import OutboxEventWriter


def get_create_project_use_case(session: AsyncSession) -> CreateProjectUseCase:
    project_repo: ProjectRepository = SQLAlchemyProjectRepository(session)
    outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(session)
    return CreateProjectUseCase(project_repo, outbox)


def get_create_api_key_use_case(session: AsyncSession) -> CreateApiKeyUseCase:
    project_repo: ProjectRepository = SQLAlchemyProjectRepository(session)
    api_key_repo: ApiKeyRepository = SQLAlchemyApiKeyRepository(session)
    outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(session)
    return CreateApiKeyUseCase(project_repo, api_key_repo, outbox)


def list_projects_use_case(session: AsyncSession):
    from modules.core.infra.repositories import SQLAlchemyProjectRepository
    repo = SQLAlchemyProjectRepository(session)
    return _ListProjectsUseCase(repo)


def get_project_by_id_use_case(session: AsyncSession):
    from modules.core.infra.repositories import SQLAlchemyProjectRepository
    repo = SQLAlchemyProjectRepository(session)
    return _GetProjectByIdUseCase(repo)


def list_api_keys_by_project_use_case(session: AsyncSession):
    from modules.core.infra.repositories import SQLAlchemyApiKeyRepository
    repo = SQLAlchemyApiKeyRepository(session)
    return _ListApiKeysByProjectUseCase(repo)


class _ListProjectsUseCase:
    def __init__(self, repo: ProjectRepository):
        self._repo = repo

    async def execute(self, organization_id=None) -> list:
        if organization_id:
            return await self._repo.list_by_organization(organization_id)
        return await self._repo.list_all()


class _GetProjectByIdUseCase:
    def __init__(self, repo: ProjectRepository):
        self._repo = repo

    async def execute(self, project_id):
        project = await self._repo.get_by_id(project_id)
        if not project:
            from modules.core.domain.errors import ProjectNotFoundError
            raise ProjectNotFoundError(project_id)
        return project


class _ListApiKeysByProjectUseCase:
    def __init__(self, repo: ApiKeyRepository):
        self._repo = repo

    async def execute(self, project_id):
        return await self._repo.list_by_project(project_id)
