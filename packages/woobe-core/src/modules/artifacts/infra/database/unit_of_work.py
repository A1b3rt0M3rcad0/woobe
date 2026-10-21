from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from shared.contracts.unit_of_work import UnitOfWork


class ArtifactsUnitOfWork(UnitOfWork):
    def __init__(self, engine: AsyncEngine):
        self._factory = async_sessionmaker(engine, expire_on_commit=False)
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError('Artifacts transaction has not started')
        return self._session

    async def __aenter__(self):
        if self._session is not None:
            raise RuntimeError('Nested artifacts transactions are not supported')
        self._session = self._factory()
        return self

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                await self.rollback()
            else:
                try:
                    await self.commit()
                except BaseException:
                    await self.rollback()
                    raise
        finally:
            await self.session.close()
            self._session = None
