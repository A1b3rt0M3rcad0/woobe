from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.repositories.base_repository import BaseRepository
from modules.tools.domain.entities import Secret, Tool
from modules.tools.domain.errors import SecretNotFoundError, ToolNotFoundError
from modules.tools.domain.repositories import SecretRepository, ToolRepository
from modules.tools.infra.mappers import (
    model_to_secret,
    model_to_tool,
    secret_to_model,
    tool_to_model,
)
from modules.tools.infra.models import SecretModel, ToolModel


class SQLAlchemyToolRepository(ToolRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._base = BaseRepository(session, ToolModel)
        self.session = session

    async def create(self, tool: Tool) -> Tool:
        model = tool_to_model(tool)
        await self._base.add(model)
        return model_to_tool(model)

    async def get_by_id(self, tool_id: UUID) -> Tool:
        model = await self._base.get_by_id(tool_id)
        if model is None:
            raise ToolNotFoundError(tool_id)
        return model_to_tool(model)

    async def list_by_project(
        self, project_id: UUID, status: str | None = None
    ) -> list[Tool]:
        stmt = select(ToolModel).where(ToolModel.project_id == project_id)
        if status:
            stmt = stmt.where(ToolModel.status == status)
        stmt = stmt.order_by(ToolModel.created_at.desc())
        result = await self.session.execute(stmt)
        return [model_to_tool(m) for m in result.scalars().all()]

    async def list_by_agent(
        self, agent_id: UUID, status: str | None = None
    ) -> list[Tool]:
        stmt = select(ToolModel).where(ToolModel.agent_id == agent_id)
        if status:
            stmt = stmt.where(ToolModel.status == status)
        stmt = stmt.order_by(ToolModel.created_at.desc())
        result = await self.session.execute(stmt)
        return [model_to_tool(m) for m in result.scalars().all()]

    async def update(self, tool: Tool) -> Tool:
        model = await self._base.get_by_id(tool.id)
        if model is None:
            raise ToolNotFoundError(tool.id)
        model.name = tool.name
        model.description = tool.description
        model.type = tool.type
        model.config = tool.config
        model.input_schema = tool.input_schema
        model.output_schema = tool.output_schema
        model.risk_level = tool.risk_level
        model.timeout_ms = tool.timeout_ms
        model.status = tool.status
        return model_to_tool(model)

    async def delete(self, tool_id: UUID) -> None:
        model = await self._base.get_by_id(tool_id)
        if model is None:
            raise ToolNotFoundError(tool_id)
        await self._base.delete(model)


class SQLAlchemySecretRepository(SecretRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._base = BaseRepository(session, SecretModel)
        self.session = session

    async def create(self, secret: Secret) -> Secret:
        model = secret_to_model(secret)
        await self._base.add(model)
        return model_to_secret(model)

    async def get_by_id(self, secret_id: UUID) -> Secret:
        model = await self._base.get_by_id(secret_id)
        if model is None:
            raise SecretNotFoundError(secret_id)
        return model_to_secret(model)

    async def get_by_name(self, project_id: UUID, name: str) -> Secret:
        stmt = select(SecretModel).where(
            SecretModel.project_id == project_id,
            SecretModel.name == name,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise SecretNotFoundError(secret_id=name)
        return model_to_secret(model)

    async def list_by_project(self, project_id: UUID) -> list[Secret]:
        stmt = (
            select(SecretModel)
            .where(SecretModel.project_id == project_id)
            .order_by(SecretModel.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return [model_to_secret(m) for m in result.scalars().all()]

    async def update(self, secret: Secret) -> Secret:
        model = await self._base.get_by_id(secret.id)
        if model is None:
            raise SecretNotFoundError(secret.id)
        model.name = secret.name
        model.type = secret.type
        model.encrypted_value = secret.encrypted_value
        model.data = secret.data
        return model_to_secret(model)

    async def delete(self, secret_id: UUID) -> None:
        model = await self._base.get_by_id(secret_id)
        if model is None:
            raise SecretNotFoundError(secret_id)
        await self._base.delete(model)

