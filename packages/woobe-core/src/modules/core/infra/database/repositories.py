from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.core.domain.entities import ApiKey, Project
from modules.core.domain.repositories import (
    ApiKeyRepository as ApiKeyRepositoryInterface,
    ProjectRepository as ProjectRepositoryInterface,
)
from modules.core.infra.database.mappers import (
    api_key_entity_to_model,
    api_key_model_to_entity,
    project_entity_to_model,
    project_model_to_entity,
)
from modules.core.infra.database.models import (
    ApiKeyModel,
    OutboxEventModel,
    ProjectModel,
)
from shared.infra.config.interface.unit_of_work import UnitOfWork
from shared.infra.objects import CursorPage
from shared.infra.repositories.base_repository import BaseSQLAlchemyRepository
from shared.messaging.outbox_writer import OutboxEventWriter


class SQLAlchemyProjectRepository(
    BaseSQLAlchemyRepository[ProjectModel], ProjectRepositoryInterface
):
    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, ProjectModel)

    async def save(self, project: Project) -> Project:
        model = await self._get_model_by_id(project.id)
        if model is None:
            model = project_entity_to_model(project)
            await self._add_model(model)
        else:
            model.workspace_id = project.workspace_id
            model.name = project.name
            model.slug = project.slug
            model.status = project.status.value
            model.data = project.data
            if project.updated_at is not None:
                model.updated_at = project.updated_at
        await self._flush()
        await self._refresh_model(model)
        return project_model_to_entity(model)

    async def get_by_id(self, project_id: UUID) -> Project | None:
        model = await self._get_model_by_id(project_id)
        return project_model_to_entity(model) if model else None

    async def get_by_workspace_and_slug(
        self, workspace_id: UUID, slug: str
    ) -> Project | None:
        result = await self._session.execute(
            select(ProjectModel).where(
                ProjectModel.workspace_id == workspace_id,
                ProjectModel.slug == slug,
            )
        )
        model = result.scalar_one_or_none()
        return project_model_to_entity(model) if model else None

    async def list_by_workspace(self, workspace_id: UUID) -> list[Project]:
        result = await self._session.execute(
            select(ProjectModel).where(ProjectModel.workspace_id == workspace_id)
        )
        return [project_model_to_entity(p) for p in result.scalars().all()]

    async def paginate_by_workspace(
        self, workspace_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Project]:
        stmt = (
            select(ProjectModel)
            .where(ProjectModel.workspace_id == workspace_id)
            .order_by(ProjectModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[project_model_to_entity(p) for p in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def delete(self, project_id: UUID) -> None:
        model = await self._get_model_by_id(project_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyApiKeyRepository(
    BaseSQLAlchemyRepository[ApiKeyModel], ApiKeyRepositoryInterface
):
    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, ApiKeyModel)

    async def save(self, api_key: ApiKey) -> ApiKey:
        model = api_key_entity_to_model(api_key)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return api_key_model_to_entity(model)

    async def update(self, api_key: ApiKey) -> ApiKey:
        model = await self._get_model_by_id(api_key.id)
        if model is None:
            raise LookupError(f"API key {api_key.id} does not exist")
        model.name = api_key.name
        model.description = api_key.description
        model.scopes = list(api_key.scopes)
        model.kind = api_key.kind.value
        model.agent_id = api_key.agent_id
        model.target_type = api_key.target_type.value if api_key.target_type else None
        model.target_id = api_key.target_id
        model.environment = api_key.environment.value if api_key.environment else None
        model.interfaces = list(api_key.interfaces)
        model.status = api_key.status.value
        model.last_used_at = api_key.last_used_at
        model.expires_at = api_key.expires_at
        model.delegation_expires_at = api_key.delegation_expires_at
        model.revoked_at = api_key.revoked_at
        model.updated_at = api_key.updated_at or model.updated_at
        await self._flush()
        await self._refresh_model(model)
        return api_key_model_to_entity(model)

    async def get_by_id(self, api_key_id: UUID) -> ApiKey | None:
        model = await self._get_model_by_id(api_key_id)
        return api_key_model_to_entity(model) if model else None

    async def update_credential_metadata(
        self,
        credential_id: UUID,
        *,
        name: str,
        description: str | None,
    ) -> ApiKey:
        result = await self._session.execute(
            select(ApiKeyModel)
            .where(ApiKeyModel.credential_id == credential_id)
            .order_by(ApiKeyModel.created_at.desc(), ApiKeyModel.id.desc())
        )
        models = list(result.scalars().all())
        if not models:
            raise LookupError(f"API key credential {credential_id} does not exist")
        for model in models:
            model.name = name
            model.description = description
        await self._flush()
        await self._refresh_model(models[0])
        return api_key_model_to_entity(models[0])

    async def get_by_key_hash(self, key_hash: bytes) -> ApiKey | None:
        result = await self._session.execute(
            select(ApiKeyModel).where(ApiKeyModel.key_hash == key_hash)
        )
        model = result.scalar_one_or_none()
        return api_key_model_to_entity(model) if model else None

    async def get_by_prefix(self, key_prefix: str) -> ApiKey | None:
        result = await self._session.execute(
            select(ApiKeyModel).where(ApiKeyModel.key_prefix == key_prefix)
        )
        model = result.scalar_one_or_none()
        return api_key_model_to_entity(model) if model else None

    async def list_by_project(self, project_id: UUID) -> list[ApiKey]:
        result = await self._session.execute(
            select(ApiKeyModel)
            .where(
                ApiKeyModel.project_id == project_id,
                ApiKeyModel.kind != "chat_surface",
            )
            .order_by(ApiKeyModel.created_at.desc())
        )
        return [api_key_model_to_entity(k) for k in result.scalars().all()]

    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[ApiKey]:
        stmt = (
            select(ApiKeyModel)
            .where(
                ApiKeyModel.project_id == project_id,
                ApiKeyModel.kind != "chat_surface",
            )
            .order_by(ApiKeyModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[api_key_model_to_entity(k) for k in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def delete(self, api_key_id: UUID) -> None:
        model = await self._get_model_by_id(api_key_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyOutboxEventWriter(OutboxEventWriter):
    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def write(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        routing_key: str,
        idempotency_key: str,
        event_version: int = 1,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        event = OutboxEventModel(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            event_version=event_version,
            routing_key=routing_key,
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self._session.add(event)
