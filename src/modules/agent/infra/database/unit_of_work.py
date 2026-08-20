from __future__ import annotations

from typing import Any

from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.database import AgentDatabase
from shared.infra.config.interface.unit_of_work import UnitOfWork


class AgentUnitOfWork(UnitOfWork):
    """Transaction boundary for Agent persistence.

    Repositories are composed explicitly outside the UoW and share this session.
    The SQLAlchemy session-factory compatibility path is infrastructure-only; module
    composition receives ``AgentDatabase`` instead of framework primitives.
    """

    def __init__(
        self,
        database: AgentDatabase | async_sessionmaker[AsyncSession],
    ) -> None:
        self._database = (
            database if isinstance(database, AgentDatabase) else AgentDatabase(database)
        )
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("AgentUnitOfWork session not started")
        return self._session

    async def commit(self) -> None:
        if self._session is not None:
            try:
                await self._session.commit()
            except PendingRollbackError:
                await self.rollback()
                raise

    async def rollback(self) -> None:
        if self._session is not None:
            await self._session.rollback()

    async def __aenter__(self) -> "AgentUnitOfWork":
        self._session = self._database.open_session()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
        if self._session is not None:
            await self._session.close()
            self._session = None
