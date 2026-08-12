from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.network.infra.database.repositories import (
    NetworkOutboxRepository,
    NetworkRepository,
    NetworkRuntimeRepository,
)
from shared.infra.config.interface.unit_of_work import UnitOfWork


class NetworkUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._networks: NetworkRepository | None = None
        self._runtime: NetworkRuntimeRepository | None = None
        self._outbox: NetworkOutboxRepository | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("NetworkUnitOfWork session not started")
        return self._session

    @property
    def networks(self) -> NetworkRepository:
        if self._networks is None:
            self._networks = NetworkRepository(self.session)
        return self._networks

    @property
    def runtime(self) -> NetworkRuntimeRepository:
        if self._runtime is None:
            self._runtime = NetworkRuntimeRepository(self.session)
        return self._runtime

    @property
    def outbox(self) -> NetworkOutboxRepository:
        if self._outbox is None:
            self._outbox = NetworkOutboxRepository(self.session)
        return self._outbox

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def __aenter__(self) -> NetworkUnitOfWork:
        self._session = self._session_factory()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._session is not None:
            if exc_type is None:
                await self._session.commit()
            else:
                await self._session.rollback()
            await self._session.close()
        self._session = None
        self._networks = None
        self._runtime = None
        self._outbox = None
