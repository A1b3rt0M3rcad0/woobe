import secrets
from datetime import UTC, datetime
from hashlib import sha256

from modules.core.domain.entities import ApiKey, Project
from modules.core.domain.errors import DuplicateSlugError, ProjectNotFoundError
from modules.core.domain.repositories import ApiKeyRepository, ProjectRepository
from modules.core.service.dtos import (
    CreateApiKeyInput,
    CreateApiKeyOutput,
    CreateProjectInput,
    CreateProjectOutput,
    GetProjectInput,
    GetProjectOutput,
    ListApiKeysInput,
    ListApiKeysOutput,
    ListProjectsInput,
    ListProjectsOutput,
    UpdateProjectInput,
    UpdateProjectOutput,
)
from shared.domain.events import OutboxEventWriter


class CreateProjectUseCase:

    def __init__(
        self,
        project_repo: ProjectRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._project_repo = project_repo
        self._outbox = outbox

    async def execute(self, input_dto: CreateProjectInput) -> CreateProjectOutput:
        existing = await self._project_repo.get_by_organization_and_slug(
            input_dto.organization_id, input_dto.slug
        )
        if existing:
            raise DuplicateSlugError(
                f"Project with slug '{input_dto.slug}' already exists in this organization"
            )

        project = Project(
            organization_id=input_dto.organization_id,
            name=input_dto.name,
            slug=input_dto.slug,
        )
        saved = await self._project_repo.save(project)

        await self._outbox.write(
            aggregate_type="project",
            aggregate_id=saved.id,
            event_type="project.created",
            payload={
                "organization_id": str(saved.organization_id),
                "name": saved.name,
                "slug": saved.slug,
            },
        )

        return CreateProjectOutput(
            id=saved.id,
            organization_id=saved.organization_id,
            name=saved.name,
            slug=saved.slug,
            status=saved.status,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )


class CreateApiKeyUseCase:

    def __init__(
        self,
        project_repo: ProjectRepository,
        api_key_repo: ApiKeyRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._project_repo = project_repo
        self._api_key_repo = api_key_repo
        self._outbox = outbox

    async def execute(self, input_dto: CreateApiKeyInput) -> CreateApiKeyOutput:
        project = await self._project_repo.get_by_id(input_dto.project_id)
        if not project:
            raise ProjectNotFoundError(input_dto.project_id)

        raw = "rai_" + secrets.token_hex(32)
        key_hash = sha256(raw.encode()).digest()
        key_prefix = raw[:10]

        api_key = ApiKey(
            project_id=input_dto.project_id,
            name=input_dto.name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=input_dto.scopes,
            created_by_user_id=input_dto.created_by_user_id,
        )
        saved = await self._api_key_repo.save(api_key)

        await self._outbox.write(
            aggregate_type="api_key",
            aggregate_id=saved.id,
            event_type="api_key.created",
            payload={
                "project_id": str(saved.project_id),
                "name": saved.name,
            },
        )

        return CreateApiKeyOutput(
            id=saved.id,
            project_id=saved.project_id,
            name=saved.name,
            key_prefix=saved.key_prefix,
            key_hash=saved.key_hash,
            status=saved.status,
            created_at=saved.created_at,
        )


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


class GetProjectByIdUseCase:

    def __init__(self, project_repo: ProjectRepository) -> None:
        self._project_repo = project_repo

    async def execute(self, input_dto: GetProjectInput) -> GetProjectOutput:
        project = await self._project_repo.get_by_id(input_dto.project_id)
        if not project:
            raise ProjectNotFoundError(input_dto.project_id)
        return GetProjectOutput(
            id=project.id,
            organization_id=project.organization_id,
            name=project.name,
            slug=project.slug,
            status=project.status,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


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


class ListApiKeysByProjectUseCase:

    def __init__(self, api_key_repo: ApiKeyRepository) -> None:
        self._api_key_repo = api_key_repo

    async def execute(self, input_dto: ListApiKeysInput) -> list[ListApiKeysOutput]:
        keys = await self._api_key_repo.list_by_project(input_dto.project_id)
        return [ListApiKeysOutput(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            status=k.status,
        ) for k in keys]
