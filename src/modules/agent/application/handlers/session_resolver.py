from __future__ import annotations

import logging
from uuid import UUID

from modules.agent.domain.entities import Session
from modules.agent.domain.enums import RuntimeSessionMode as SessionMode, SessionStatus
from modules.agent.domain.errors import (
    SessionInvalidStatusError,
    SessionOwnershipMismatchError,
)
from modules.agent.domain.repositories import SessionRepository

logger = logging.getLogger(__name__)

_INVALID_STATUSES = {SessionStatus.CLOSED, SessionStatus.EXPIRED, SessionStatus.ERROR}


class SessionResolver:
    def __init__(self, session_repo: SessionRepository) -> None:
        self._session_repo = session_repo

    async def resolve(
        self,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID | None,
        tenant_id: str | None,
        user_id: str | None,
        session_mode: str,
    ) -> Session | None:
        if session_mode == "stateless":
            if session_id is not None:
                logger.info(
                    "session_id=%s ignored in stateless mode (project=%s, agent=%s)",
                    session_id, project_id, agent_id,
                )
            return None

        if session_id is not None:
            return await self._resolve_existing(session_id, project_id, agent_id, tenant_id, user_id)

        return await self._create_new(project_id, agent_id, tenant_id, user_id)

    async def _resolve_existing(
        self,
        session_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        tenant_id: str | None,
        user_id: str | None,
    ) -> Session:
        session = await self._session_repo.get_by_id(session_id)

        self._raise_if_ownership_mismatch(session, project_id, agent_id, tenant_id, user_id)
        self._raise_if_invalid_status(session)

        return session

    async def _create_new(
        self,
        project_id: UUID,
        agent_id: UUID,
        tenant_id: str | None,
        user_id: str | None,
    ) -> Session:
        session = Session(
            project_id=project_id,
            agent_id=agent_id,
            external_session_id=None,
            tenant_id=tenant_id,
            user_id=user_id,
            mode=SessionMode.CHAT,
        )
        return await self._session_repo.create(session)

    async def validate_existing(
        self,
        session_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        tenant_id: str | None,
        user_id: str | None,
    ) -> Session:
        session = await self._session_repo.get_by_id(session_id)
        self._raise_if_ownership_mismatch(session, project_id, agent_id, tenant_id, user_id)
        self._raise_if_invalid_status(session)
        return session

    def _raise_if_ownership_mismatch(
        self,
        session: Session,
        project_id: UUID,
        agent_id: UUID,
        tenant_id: str | None,
        user_id: str | None,
    ) -> None:
        if session.project_id != project_id:
            raise SessionOwnershipMismatchError(session.id)

        if session.agent_id != agent_id:
            raise SessionOwnershipMismatchError(session.id)

        if tenant_id is not None and session.tenant_id is not None and session.tenant_id != tenant_id:
            raise SessionOwnershipMismatchError(session.id)

        if user_id is not None and session.user_id is not None and session.user_id != user_id:
            raise SessionOwnershipMismatchError(session.id)

    def _raise_if_invalid_status(self, session: Session) -> None:
        if session.status in _INVALID_STATUSES:
            raise SessionInvalidStatusError(session.id, session.status.value)
