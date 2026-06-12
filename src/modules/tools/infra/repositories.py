from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.config.interface.unit_of_work import UnitOfWork

from modules.tools.domain.entities import Secret, Tool
from modules.tools.domain.errors import SecretNotFoundError, ToolNotFoundError
from modules.tools.domain.repositories import SecretRepository, ToolRepository
from modules.tools.infra.mappers import (
    model_to_secret,
    model_to_tool,
    secret_to_model,
    tool_to_model,
)
from modules.tools.infra.models import OutboxEventModel, SecretModel, ToolModel
from shared.domain.events import OutboxEventWriter
from shared.domain.objects import CursorPage
from shared.infra.repositories.base_repository import BaseSQLAlchemyRepository


class SQLAlchemyToolRepository(ToolRepository):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, ToolModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def create(self, tool: Tool) -> Tool:
        model = tool_to_model(tool)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return model_to_tool(model)

    async def get_by_id(self, tool_id: UUID) -> Tool:
        model = await self._base._get_model_by_id(tool_id)
        if model is None:
            raise ToolNotFoundError(tool_id)
        return model_to_tool(model)

    async def list_by_project(
        self, project_id: UUID, status: str | None = None
    ) -> list[Tool]:
        # TODO: Remove after pagination migration
        stmt = select(ToolModel).where(ToolModel.project_id == project_id)
        if status:
            stmt = stmt.where(ToolModel.status == status)
        stmt = stmt.order_by(ToolModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [model_to_tool(m) for m in result.scalars().all()]

    async def list_by_agent(
        self, agent_id: UUID, status: str | None = None
    ) -> list[Tool]:
        # TODO: Remove after pagination migration
        stmt = select(ToolModel).where(ToolModel.agent_id == agent_id)
        if status:
            stmt = stmt.where(ToolModel.status == status)
        stmt = stmt.order_by(ToolModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [model_to_tool(m) for m in result.scalars().all()]

    async def paginate_by_project(
        self, project_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Tool]:
        stmt = select(ToolModel).where(ToolModel.project_id == project_id)
        if status:
            stmt = stmt.where(ToolModel.status == status)
        stmt = stmt.order_by(ToolModel.id.desc())
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_tool(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def paginate_by_agent(
        self, agent_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Tool]:
        stmt = select(ToolModel).where(ToolModel.agent_id == agent_id)
        if status:
            stmt = stmt.where(ToolModel.status == status)
        stmt = stmt.order_by(ToolModel.id.desc())
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_tool(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def update(self, tool: Tool) -> Tool:
        model = await self._base._get_model_by_id(tool.id)
        if model is None:
            raise ToolNotFoundError(tool.id)
        model.name = tool.name
        model.description = tool.description
        model.agent_id = tool.agent_id
        model.type = tool.type
        model.config = tool.config
        model.input_schema = tool.input_schema
        model.output_schema = tool.output_schema
        model.risk_level = tool.risk_level
        model.timeout_ms = tool.timeout_ms
        model.status = tool.status
        return model_to_tool(model)

    async def delete(self, tool_id: UUID) -> None:
        model = await self._base._get_model_by_id(tool_id)
        if model is None:
            raise ToolNotFoundError(tool_id)
        await self._base._delete_model(model)


class SQLAlchemySecretRepository(SecretRepository):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, SecretModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def create(self, secret: Secret) -> Secret:
        model = secret_to_model(secret)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return model_to_secret(model)

    async def get_by_id(self, secret_id: UUID) -> Secret:
        model = await self._base._get_model_by_id(secret_id)
        if model is None:
            raise SecretNotFoundError(secret_id)
        return model_to_secret(model)

    async def get_by_name(self, project_id: UUID, name: str) -> Secret:
        stmt = select(SecretModel).where(
            SecretModel.project_id == project_id,
            SecretModel.name == name,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise SecretNotFoundError(secret_id=name)
        return model_to_secret(model)

    async def list_by_project(self, project_id: UUID) -> list[Secret]:
        # TODO: Remove after pagination migration
        stmt = (
            select(SecretModel)
            .where(SecretModel.project_id == project_id)
            .order_by(SecretModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [model_to_secret(m) for m in result.scalars().all()]

    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Secret]:
        stmt = (
            select(SecretModel)
            .where(SecretModel.project_id == project_id)
            .order_by(SecretModel.id.desc())
        )
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_secret(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def update(self, secret: Secret) -> Secret:
        model = await self._base._get_model_by_id(secret.id)
        if model is None:
            raise SecretNotFoundError(secret.id)
        model.name = secret.name
        model.type = secret.type
        model.encrypted_value = secret.encrypted_value
        model.data = secret.data
        return model_to_secret(model)

    async def delete(self, secret_id: UUID) -> None:
        model = await self._base._get_model_by_id(secret_id)
        if model is None:
            raise SecretNotFoundError(secret_id)
        await self._base._delete_model(model)


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
        event_version: int = 1,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        event = OutboxEventModel(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self._session.add(event)

