from typing import Optional, Self

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


class SessionManager:

    def __init__(self, async_engine: AsyncEngine) -> None:
        self.__session: Optional[AsyncSession] = None
        self._async_engine = async_engine

    @property
    def session(self) -> AsyncSession:
        if self.__session is not None:
            return self.__session
        raise RuntimeError("SessionManager not started")

    async def rollback(self) -> None:
        if self.__session is not None:
            await self.__session.rollback()
            return
        raise RuntimeError("SessionManager not started")

    async def commit(self) -> None:
        if self.__session is not None:
            await self.__session.commit()
            return
        raise RuntimeError("SessionManager not started")

    async def __aenter__(self) -> Self:
        async_session = async_sessionmaker(
            bind=self._async_engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )()
        self.__session = async_session
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type:
            await self.rollback()
        else:
            await self.commit()

        if self.__session is not None:
            await self.__session.close()

        self.__session = None
