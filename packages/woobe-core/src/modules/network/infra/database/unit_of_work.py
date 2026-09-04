from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from shared.infra.config.interface.unit_of_work import UnitOfWork


class NetworkUnitOfWork(UnitOfWork):
    def __init__(self, engine: AsyncEngine) -> None:
        self._session_factory = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("NetworkUnitOfWork session not started")
        return self._session

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
