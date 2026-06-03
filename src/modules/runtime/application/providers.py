from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.runtime.domain.repositories import MessageRepository, SessionRepository
from modules.runtime.infra.repositories import (
    SQLAlchemyMessageRepository,
    SQLAlchemySessionRepository,
)
from modules.runtime.service.use_cases import (
    CreateSessionUseCase,
    SendMessageUseCase,
)


def provide_create_session_uc(session: AsyncSession) -> CreateSessionUseCase:
    repo: SessionRepository = SQLAlchemySessionRepository(session)
    return CreateSessionUseCase(session, repo)


def provide_send_message_uc(session: AsyncSession) -> SendMessageUseCase:
    session_repo: SessionRepository = SQLAlchemySessionRepository(session)
    message_repo: MessageRepository = SQLAlchemyMessageRepository(session)
    return SendMessageUseCase(session, session_repo, message_repo)


async def provide_list_messages(session: AsyncSession, session_id: UUID, offset: int = 0, limit: int = 100):
    repo = SQLAlchemyMessageRepository(session)
    return await repo.list_by_session(session_id, offset, limit)
