from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.runtime.domain.entities import Message
from modules.runtime.infra.repositories import (
    SQLAlchemyMessageRepository,
    SQLAlchemySessionRepository,
)
from modules.runtime.service.use_cases import CreateSessionUseCase, SendMessageUseCase


def provide_create_session_uc(session: AsyncSession) -> CreateSessionUseCase:
    repo = SQLAlchemySessionRepository(session)
    return CreateSessionUseCase(session=session, repo=repo)


def provide_send_message_uc(session: AsyncSession) -> SendMessageUseCase:
    session_repo = SQLAlchemySessionRepository(session)
    message_repo = SQLAlchemyMessageRepository(session)
    return SendMessageUseCase(
        session=session, session_repo=session_repo, message_repo=message_repo
    )


async def provide_list_messages(
    session: AsyncSession,
    session_id: UUID,
    offset: int = 0,
    limit: int = 100,
) -> list[Message]:
    repo = SQLAlchemyMessageRepository(session)
    return await repo.list_by_session(session_id, offset=offset, limit=limit)

