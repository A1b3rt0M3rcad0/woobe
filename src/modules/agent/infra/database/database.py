from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class AgentDatabase:
    """Agent-owned database runtime used by the module composition root."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Infrastructure-only compatibility for existing runtime services."""
        return self._session_factory

    def open_session(self) -> AsyncSession:
        return self._session_factory()

    def __call__(self) -> AsyncSession:
        return self.open_session()
