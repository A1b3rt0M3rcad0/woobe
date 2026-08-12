from __future__ import annotations

from typing import Any

from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.config.interface.unit_of_work import UnitOfWork

from modules.core.infra.database.repositories import (
    SQLAlchemyApiKeyRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyProjectRepository,
)
from modules.core.infra.database.contextual_project_overview_reader import (
    ContextualProjectOverviewReader,
)


class CoreUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._projects: SQLAlchemyProjectRepository | None = None
        self._api_keys: SQLAlchemyApiKeyRepository | None = None
        self._outbox: SQLAlchemyOutboxEventWriter | None = None
        self._project_overview: ContextualProjectOverviewReader | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("CoreUnitOfWork session not started")
        return self._session

    @property
    def projects(self) -> SQLAlchemyProjectRepository:
        if self._projects is None:
            self._projects = SQLAlchemyProjectRepository(self)
        return self._projects

    @property
    def api_keys(self) -> SQLAlchemyApiKeyRepository:
        if self._api_keys is None:
            self._api_keys = SQLAlchemyApiKeyRepository(self)
        return self._api_keys

    @property
    def outbox(self) -> SQLAlchemyOutboxEventWriter:
        if self._outbox is None:
            self._outbox = SQLAlchemyOutboxEventWriter(self)
        return self._outbox

    @property
    def project_overview(self) -> ContextualProjectOverviewReader:
        if self._project_overview is None:
            self._project_overview = ContextualProjectOverviewReader(self)
        return self._project_overview

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

    async def __aenter__(self) -> CoreUnitOfWork:
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
        self._projects = None
        self._api_keys = None
        self._outbox = None
        self._project_overview = None
