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
