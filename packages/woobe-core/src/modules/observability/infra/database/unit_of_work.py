from __future__ import annotations

from typing import Self

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from shared.infra.config.interface.unit_of_work import UnitOfWork


class ObservabilityUnitOfWork(UnitOfWork):
    def __init__(self, engine: AsyncEngine) -> None:
        self._session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self._session: AsyncSession | None = None
        self._read_only = False

    def mark_read_only(self) -> Self:
        self._read_only = True
        return self

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("ObservabilityUnitOfWork not entered")
        return self._session

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        session = self._session
        try:
            if session is None:
                return
            if exc_type is not None or self._read_only:
                await session.rollback()
            else:
                await session.commit()
        finally:
            if session is not None:
                await session.close()
            self._session = None

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
