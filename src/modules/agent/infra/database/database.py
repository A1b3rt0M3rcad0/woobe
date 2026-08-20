from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class AgentDatabase:
    """Agent-owned database runtime used by the module composition root."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    def open_session(self) -> AsyncSession:
        return self._session_factory()

    def __call__(self) -> AsyncSession:
        return self.open_session()


AgentDatabaseInput = AgentDatabase | async_sessionmaker[AsyncSession]


def coerce_agent_database(database: AgentDatabaseInput) -> AgentDatabase:
    if isinstance(database, AgentDatabase):
        return database
    return AgentDatabase(database)


def agent_session_factory(
    database: AgentDatabaseInput,
) -> async_sessionmaker[AsyncSession]:
    return coerce_agent_database(database).session_factory
