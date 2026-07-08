from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, add_mapped_attribute, mapped_column

from modules.agent.domain.entities import Agent, AgentRelease, ProviderModel
from modules.agent.domain.enums import ProviderModelStatus, ReleaseStatus
from modules.agent.infra.database.models import AgentModel, AgentReleaseModel
from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository, SQLAlchemyAgentRepository
from shared.infra.config.interface.unit_of_work import UnitOfWork
from shared.infra.database.base import BaseModel
from shared.infra.objects import CursorPage
from shared.infra.repositories.base_repository import BaseSQLAlchemyRepository


class ProviderModelModel(BaseModel):
    __tablename__ = "provider_models"
    __table_args__ = (
        UniqueConstraint("project_id", "provider_credential_id", "model", name="uq_provider_models_project_credential_model"),
        Index("ix_provider_models_project_id", "project_id"),
        Index("ix_provider_models_credential_id", "provider_credential_id"),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    provider_credential_id: Mapped[UUID] = mapped_column(ForeignKey("agent.provider_credentials.id"))
    name: Mapped[str] = mapped_column(String(255))
    model: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active")
    meta: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)


def _register_provider_model_refs() -> None:
    for model in (AgentModel, AgentReleaseModel):
        for name in ("provider_model_id", "fallback_provider_model_id"):
            if hasattr(model, name):
                continue
            column = mapped_column(ForeignKey("agent.provider_models.id"), nullable=True)
            add_mapped_attribute(model, name, cast(Any, column))


_register_provider_model_refs()


def _to_entity(model: ProviderModelModel) -> ProviderModel:
    return ProviderModel(
        id=model.id,
        project_id=model.project_id,
        provider_credential_id=model.provider_credential_id,
        name=model.name,
        model=model.model,
        status=ProviderModelStatus(model.status),
        metadata=model.meta or {},
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_model(entity: ProviderModel) -> ProviderModelModel:
    return ProviderModelModel(
        id=entity.id,
        project_id=entity.project_id,
        provider_credential_id=entity.provider_credential_id,
        name=entity.name,
        model=entity.model,
        status=getattr(entity.status, "value", entity.status),
        meta=entity.metadata or None,
    )


class SQLAlchemyProviderModelRepository(BaseSQLAlchemyRepository[ProviderModelModel]):
    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, ProviderModelModel)

    async def save(self, provider_model: ProviderModel) -> ProviderModel:
        model = _to_model(provider_model)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return _to_entity(model)

    async def get_by_id(self, provider_model_id: UUID) -> ProviderModel | None:
        model = await self._get_model_by_id(provider_model_id)
        return _to_entity(model) if model else None

    async def list_by_project(self, project_id: UUID) -> list[ProviderModel]:
        result = await self._session.execute(
            select(ProviderModelModel).where(ProviderModelModel.project_id == project_id).order_by(ProviderModelModel.created_at.desc())
        )
        return [_to_entity(item) for item in result.scalars().all()]

    async def list_by_credential(self, credential_id: UUID) -> list[ProviderModel]:
        result = await self._session.execute(
            select(ProviderModelModel).where(ProviderModelModel.provider_credential_id == credential_id).order_by(ProviderModelModel.created_at.desc())
        )
        return [_to_entity(item) for item in result.scalars().all()]

    async def paginate_by_project(self, project_id: UUID, *, limit: int = 50, cursor: str | None = None) -> CursorPage[ProviderModel]:
        stmt = select(ProviderModelModel).where(ProviderModelModel.project_id == project_id).order_by(ProviderModelModel.id.desc())
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(items=[_to_entity(item) for item in page.items], cursor=page.cursor, next_cursor=page.next_cursor, has_next=page.has_next, total=page.total)

    async def update(self, provider_model: ProviderModel) -> ProviderModel:
        model = await self._get_model_by_id(provider_model.id)
        if model is None:
            from modules.agent.domain.errors import ModelConfigNotFoundError
            raise ModelConfigNotFoundError
        model.provider_credential_id = provider_model.provider_credential_id
        model.name = provider_model.name
        model.model = provider_model.model
        model.status = getattr(provider_model.status, "value", provider_model.status)
        model.meta = provider_model.metadata or None
        await self._flush()
        return _to_entity(model)

    async def delete(self, provider_model_id: UUID) -> None:
        model = await self._get_model_by_id(provider_model_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyAgentRepositoryWithProviderModels(SQLAlchemyAgentRepository):
    async def save(self, agent: Agent) -> Agent:
        saved = await super().save(agent)
        await self._write_refs(agent)
        return await self.get_by_id(saved.id) or saved

    async def update(self, agent: Agent) -> Agent:
        saved = await super().update(agent)
        await self._write_refs(agent)
        return await self.get_by_id(saved.id) or saved

    async def get_by_id(self, agent_id: UUID) -> Agent | None:
        return await self._read_refs(await super().get_by_id(agent_id))

    async def list_by_project(self, project_id: UUID) -> list[Agent]:
        return [await self._read_refs(item) for item in await super().list_by_project(project_id)]

    async def paginate_by_project(self, project_id: UUID, *, limit: int = 50, cursor: str | None = None):
        page = await super().paginate_by_project(project_id, limit=limit, cursor=cursor)
        page.items = [await self._read_refs(item) for item in page.items]
        return page

    async def _read_refs(self, agent: Agent | None) -> Agent | None:
        if agent is None:
            return None
        model = await self._get_model_by_id(agent.id)
        if model is not None:
            agent.provider_model_id = getattr(model, "provider_model_id", None)
            agent.fallback_provider_model_id = getattr(model, "fallback_provider_model_id", None)
        return agent

    async def _write_refs(self, agent: Agent) -> None:
        model = await self._get_model_by_id(agent.id)
        if model is not None:
            setattr(model, "provider_model_id", agent.provider_model_id)
            setattr(model, "fallback_provider_model_id", agent.fallback_provider_model_id)
            await self._flush()


class SQLAlchemyAgentReleaseRepositoryWithProviderModels(SQLAlchemyAgentReleaseRepository):
    async def save(self, release: AgentRelease) -> AgentRelease:
        saved = await super().save(release)
        await self._write_refs(release)
        return await self.get_by_id(saved.id) or saved

    async def get_by_id(self, release_id: UUID) -> AgentRelease | None:
        return await self._read_refs(await super().get_by_id(release_id))

    async def get_active_production(self, agent_id: UUID) -> AgentRelease | None:
        return await self._read_refs(await super().get_active_production(agent_id))

    async def list_by_agent(self, agent_id: UUID) -> list[AgentRelease]:
        return [await self._read_refs(item) for item in await super().list_by_agent(agent_id)]

    async def list_by_status(self, agent_id: UUID, status: ReleaseStatus) -> list[AgentRelease]:
        return [await self._read_refs(item) for item in await super().list_by_status(agent_id, status)]

    async def _read_refs(self, release: AgentRelease | None) -> AgentRelease | None:
        if release is None:
            return None
        model = await self._get_model_by_id(release.id)
        if model is not None:
            release.provider_model_id = getattr(model, "provider_model_id", None)
            release.fallback_provider_model_id = getattr(model, "fallback_provider_model_id", None)
        return release

    async def _write_refs(self, release: AgentRelease) -> None:
        model = await self._get_model_by_id(release.id)
        if model is not None:
            setattr(model, "provider_model_id", release.provider_model_id)
            setattr(model, "fallback_provider_model_id", release.fallback_provider_model_id)
            await self._flush()
