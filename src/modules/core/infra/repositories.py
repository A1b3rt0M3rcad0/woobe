from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.core.domain.entities import ApiKey, Project
from modules.core.domain.repositories import (
    ApiKeyRepository as ApiKeyRepositoryInterface,
    ProjectRepository as ProjectRepositoryInterface,
)
from modules.core.infra.mappers import (
    api_key_entity_to_model,
    api_key_model_to_entity,
    project_entity_to_model,
    project_model_to_entity,
)
from modules.core.infra.models import ApiKeyModel, OutboxEventModel, ProjectModel
from shared.domain.events import OutboxEventWriter
from shared.infra.repositories.base_repository import BaseRepository


class SQLAlchemyProjectRepository(
    BaseRepository[ProjectModel], ProjectRepositoryInterface
):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ProjectModel)

    async def save(self, project: Project) -> Project:
        model = project_entity_to_model(project)
        self.session.add(model)
        await self.session.flush()
        return project_model_to_entity(model)

    async def get_by_id(self, project_id: UUID) -> Project | None:
        model = await super().get_by_id(project_id)
        return project_model_to_entity(model) if model else None

    async def get_by_organization_and_slug(
        self, organization_id: UUID, slug: str
    ) -> Project | None:
        result = await self.session.execute(
            select(ProjectModel).where(
                ProjectModel.organization_id == organization_id,
                ProjectModel.slug == slug,
            )
        )
        model = result.scalar_one_or_none()
        return project_model_to_entity(model) if model else None

    async def list_by_organization(
        self, organization_id: UUID
    ) -> list[Project]:
        result = await self.session.execute(
            select(ProjectModel).where(
                ProjectModel.organization_id == organization_id
            )
        )
        return [project_model_to_entity(p) for p in result.scalars().all()]

    async def delete(self, project_id: UUID) -> None:
        model = await super().get_by_id(project_id)
        if model:
            await self.session.delete(model)


class SQLAlchemyApiKeyRepository(
    BaseRepository[ApiKeyModel], ApiKeyRepositoryInterface
):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ApiKeyModel)

    async def save(self, api_key: ApiKey) -> ApiKey:
        model = api_key_entity_to_model(api_key)
        self.session.add(model)
        await self.session.flush()
        return api_key_model_to_entity(model)

    async def get_by_id(self, api_key_id: UUID) -> ApiKey | None:
        model = await super().get_by_id(api_key_id)
        return api_key_model_to_entity(model) if model else None

    async def get_by_key_hash(self, key_hash: bytes) -> ApiKey | None:
        result = await self.session.execute(
            select(ApiKeyModel).where(ApiKeyModel.key_hash == key_hash)
        )
        model = result.scalar_one_or_none()
        return api_key_model_to_entity(model) if model else None

    async def list_by_project(self, project_id: UUID) -> list[ApiKey]:
        result = await self.session.execute(
            select(ApiKeyModel).where(ApiKeyModel.project_id == project_id)
        )
        return [api_key_model_to_entity(k) for k in result.scalars().all()]

    async def delete(self, api_key_id: UUID) -> None:
        model = await super().get_by_id(api_key_id)
        if model:
            await self.session.delete(model)


class SQLAlchemyOutboxEventWriter(OutboxEventWriter):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        event = OutboxEventModel(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload or {},
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self._session.add(event)
