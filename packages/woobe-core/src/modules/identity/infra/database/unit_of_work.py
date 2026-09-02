from __future__ import annotations

from typing import Any

from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from modules.identity.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUserRepository,
    SQLAlchemyUserSessionRepository,
    SQLAlchemyWorkspaceInviteRepository,
    SQLAlchemyWorkspaceMemberRepository,
    SQLAlchemyWorkspaceRepository,
)
from shared.infra.config.interface.unit_of_work import UnitOfWork


class IdentityUnitOfWork(UnitOfWork):
    def __init__(
        self,
        engine: AsyncEngine | async_sessionmaker[AsyncSession],
    ) -> None:
        if isinstance(engine, async_sessionmaker):
            self._session_factory = engine
        else:
            self._session_factory = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        self._session: AsyncSession | None = None
        self._users: SQLAlchemyUserRepository | None = None
        self._workspaces: SQLAlchemyWorkspaceRepository | None = None
        self._members: SQLAlchemyWorkspaceMemberRepository | None = None
        self._invites: SQLAlchemyWorkspaceInviteRepository | None = None
        self._user_sessions: SQLAlchemyUserSessionRepository | None = None
        self._outbox: SQLAlchemyOutboxEventWriter | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("IdentityUnitOfWork session not started")
        return self._session

    @property
    def users(self) -> SQLAlchemyUserRepository:
        if self._users is None:
            self._users = SQLAlchemyUserRepository(self)
        return self._users

    @property
    def workspaces(self) -> SQLAlchemyWorkspaceRepository:
        if self._workspaces is None:
            self._workspaces = SQLAlchemyWorkspaceRepository(self)
        return self._workspaces

    @property
    def members(self) -> SQLAlchemyWorkspaceMemberRepository:
        if self._members is None:
            self._members = SQLAlchemyWorkspaceMemberRepository(self)
        return self._members

    @property
    def invites(self) -> SQLAlchemyWorkspaceInviteRepository:
        if self._invites is None:
            self._invites = SQLAlchemyWorkspaceInviteRepository(self)
        return self._invites

    @property
    def user_sessions(self) -> SQLAlchemyUserSessionRepository:
        if self._user_sessions is None:
            self._user_sessions = SQLAlchemyUserSessionRepository(self)
        return self._user_sessions

    @property
    def outbox(self) -> SQLAlchemyOutboxEventWriter:
        if self._outbox is None:
            self._outbox = SQLAlchemyOutboxEventWriter(self)
        return self._outbox

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

    async def __aenter__(self) -> "IdentityUnitOfWork":
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
        self._users = None
        self._workspaces = None
        self._members = None
        self._invites = None
        self._user_sessions = None
        self._outbox = None
