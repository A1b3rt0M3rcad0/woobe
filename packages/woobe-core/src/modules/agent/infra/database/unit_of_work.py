from __future__ import annotations

from typing import Any

from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from shared.infra.config.interface.unit_of_work import UnitOfWork


class AgentUnitOfWork(UnitOfWork):
    """Sole transaction/session owner for Agent persistence and short read scopes."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        self._read_only = False
        self._session: AsyncSession | None = None

    def mark_read_only(self) -> "AgentUnitOfWork":
        """Make this scope rollback on exit so read paths never emit COMMIT."""

        self._read_only = True
        return self

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("AgentUnitOfWork session not started")
        return self._session

    async def validate_revision(self, request) -> None:
        expected = getattr(request, "metadata", {}).get("expected_agent_revision")
        if expected is None:
            return
        from uuid import UUID
        from modules.agent.infra.database.models import AgentModel
        from shared.contracts.errors import ConflictError, ValidationError, NotFoundError
        raw = str(expected)
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        if not raw.isascii() or not raw.isdigit() or int(raw) < 1:
            raise ValidationError("Expected a positive Agent revision")
        identifier = request.path_params.get("agent_id")
        if identifier is None:
            raise ValidationError("Agent revision requires its resource identity")
        agent = await self.session.get(AgentModel, UUID(str(identifier)), with_for_update=True, populate_existing=True)
        if agent is None:
            raise NotFoundError("Agent is unavailable")
        if agent.revision != int(raw):
            raise ConflictError("Agent Draft revision changed; pull before updating")

    async def commit(self) -> None:
        if self._read_only:
            raise RuntimeError("Read-only AgentUnitOfWork cannot commit")
        if self._session is not None:
            try:
                await self._session.commit()
            except StaleDataError:
                await self.rollback()
                from shared.contracts.errors import ConflictError
                raise ConflictError("Agent revision changed during this operation") from None
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
        if isinstance(exc_val, StaleDataError):
            from shared.contracts.errors import ConflictError
            raise ConflictError("Agent revision changed during this operation") from None
