from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.tools.domain.entities import Tool
from modules.tools.infra.repositories import (
    SQLAlchemySecretRepository,
    SQLAlchemyToolRepository,
)
from modules.tools.service.use_cases import CreateSecretUseCase, CreateToolUseCase


def provide_create_tool_uc(session: AsyncSession) -> CreateToolUseCase:
    repo = SQLAlchemyToolRepository(session)
    return CreateToolUseCase(session=session, repo=repo)


def provide_create_secret_uc(session: AsyncSession) -> CreateSecretUseCase:
    repo = SQLAlchemySecretRepository(session)
    return CreateSecretUseCase(session=session, repo=repo)


async def provide_list_tools_by_agent(
    session: AsyncSession, agent_id: UUID
) -> list[Tool]:
    repo = SQLAlchemyToolRepository(session)
    return await repo.list_by_agent(agent_id)

