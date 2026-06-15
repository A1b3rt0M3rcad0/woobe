from __future__ import annotations

from typing import Any

from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.config.interface.unit_of_work import UnitOfWork

from modules.observability.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyTraceEventRepository,
    SQLAlchemyTraceRepository,
)


class ObservabilityUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._traces: SQLAlchemyTraceRepository | None = None
        self._trace_events: SQLAlchemyTraceEventRepository | None = None
        self._outbox: SQLAlchemyOutboxEventWriter | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("ObservabilityUnitOfWork session not started")
        return self._session

    @property
    def traces(self) -> SQLAlchemyTraceRepository:
        if self._traces is None:
            self._traces = SQLAlchemyTraceRepository(self)
        return self._traces

    @property
    def trace_events(self) -> SQLAlchemyTraceEventRepository:
        if self._trace_events is None:
            self._trace_events = SQLAlchemyTraceEventRepository(self)
        return self._trace_events

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

    async def __aenter__(self) -> ObservabilityUnitOfWork:
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
        self._traces = None
        self._trace_events = None
        self._outbox = None
