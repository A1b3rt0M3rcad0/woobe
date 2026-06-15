from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyMessageRepository, SQLAlchemyRuntimeOutboxEventWriter, SQLAlchemySessionRepository
from modules.agent.application.use_cases import SendMessageUseCase
from modules.agent.presentation.controllers.send_message_controller import SendMessageController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def send_message_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    session_repo = SQLAlchemySessionRepository(uow)
    message_repo = SQLAlchemyMessageRepository(uow)
    outbox = SQLAlchemyRuntimeOutboxEventWriter(uow)
    use_case = SendMessageUseCase(session_repo, message_repo, outbox)
    controller = SendMessageController(use_case)
    return TransactionalHandler(uow, controller.handle)
