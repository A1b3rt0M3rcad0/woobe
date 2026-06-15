from __future__ import annotations

from typing import Any

from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.config.interface.unit_of_work import UnitOfWork

from modules.tools.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemySecretRepository,
    SQLAlchemyToolRepository,
)


class ToolsUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._tools: SQLAlchemyToolRepository | None = None
        self._secrets: SQLAlchemySecretRepository | None = None
        self._outbox: SQLAlchemyOutboxEventWriter | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("ToolsUnitOfWork session not started")
        return self._session

    @property
    def tools(self) -> SQLAlchemyToolRepository:
        if self._tools is None:
            self._tools = SQLAlchemyToolRepository(self.session)
        return self._tools

    @property
    def secrets(self) -> SQLAlchemySecretRepository:
        if self._secrets is None:
            self._secrets = SQLAlchemySecretRepository(self.session)
        return self._secrets

    @property
    def outbox(self) -> SQLAlchemyOutboxEventWriter:
        if self._outbox is None:
            self._outbox = SQLAlchemyOutboxEventWriter(self.session)
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

    async def __aenter__(self) -> ToolsUnitOfWork:
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
        self._tools = None
        self._secrets = None
        self._outbox = None
