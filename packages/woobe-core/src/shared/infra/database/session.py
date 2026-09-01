from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from shared.infra.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    if settings.environment.strip().lower() == "test":
        return create_async_engine(
            url=settings.database_url,
            echo=settings.debug,
            poolclass=NullPool,
        )

    return create_async_engine(
        url=settings.database_url,
        echo=settings.debug,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
