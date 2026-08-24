from __future__ import annotations

from typing import Any

from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from shared.infra.config.interface.unit_of_work import UnitOfWork


class AgentUnitOfWork(UnitOfWork):
    """Sole transaction/session owner for Agent persistence and short read scopes."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | AsyncEngine,
        *,
        read_only: bool = False,
    ) -> None:
        if isinstance(session_factory, AsyncEngine):
            session_factory = async_sessionmaker(
                bind=session_factory,
                expire_on_commit=False,
                class_=AsyncSession,
            )
        self._session_factory = session_factory
        self._read_only = read_only
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("AgentUnitOfWork session not started")
        return self._session

    async def commit(self) -> None:
        if self._read_only:
            raise RuntimeError("Read-only AgentUnitOfWork cannot commit")
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
        self._session = self._session_factory()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None or self._read_only:
            await self.rollback()
        else:
            await self.commit()
        if self._session is not None:
            await self._session.close()
            self._session = None
