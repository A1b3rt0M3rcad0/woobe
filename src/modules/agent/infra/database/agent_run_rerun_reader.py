from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.domain.run import AgentRun
from modules.agent.infra.database.agent_run_repository import SQLAlchemyAgentRunRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


class SQLAlchemyAgentRunRerunReader:
    """Read one Agent Run in a short read-only database scope."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, run_id: UUID) -> AgentRun | None:
        async with AgentUnitOfWork(self._session_factory, read_only=True) as uow:
            return await SQLAlchemyAgentRunRepository(uow).get_by_id(run_id)
