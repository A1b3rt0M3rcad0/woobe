from __future__ import annotations

from typing import Any

from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.config.interface.unit_of_work import UnitOfWork

from modules.metering.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUsageDailyAgentRepository,
    SQLAlchemyUsageDailyProjectRepository,
    SQLAlchemyUsageEventRepository,
)


class MeteringUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._usage_events: SQLAlchemyUsageEventRepository | None = None
        self._usage_daily_projects: SQLAlchemyUsageDailyProjectRepository | None = None
        self._usage_daily_agents: SQLAlchemyUsageDailyAgentRepository | None = None
        self._outbox: SQLAlchemyOutboxEventWriter | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("MeteringUnitOfWork session not started")
        return self._session

    @property
    def usage_events(self) -> SQLAlchemyUsageEventRepository:
        if self._usage_events is None:
            self._usage_events = SQLAlchemyUsageEventRepository(self)
        return self._usage_events

    @property
    def usage_daily_projects(self) -> SQLAlchemyUsageDailyProjectRepository:
        if self._usage_daily_projects is None:
            self._usage_daily_projects = SQLAlchemyUsageDailyProjectRepository(self)
        return self._usage_daily_projects

    @property
    def usage_daily_agents(self) -> SQLAlchemyUsageDailyAgentRepository:
        if self._usage_daily_agents is None:
            self._usage_daily_agents = SQLAlchemyUsageDailyAgentRepository(self)
        return self._usage_daily_agents

    @property
    def outbox(self) -> SQLAlchemyOutboxEventWriter:
        if self._outbox is None:
            self._outbox = SQLAlchemyOutboxEventWriter(self)
        return self._outbox

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

    async def __aenter__(self) -> MeteringUnitOfWork:
        self._session = self._session_factory()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._usage_events = None
        self._usage_daily_projects = None
        self._usage_daily_agents = None
        self._outbox = None
