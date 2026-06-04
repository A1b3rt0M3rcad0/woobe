from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.runtime.infra.repositories import SQLAlchemyMessageRepository, SQLAlchemyOutboxEventWriter, SQLAlchemySessionRepository
from modules.runtime.service.use_cases import SendMessageUseCase
from modules.runtime.presentation.controllers.send_message_controller import SendMessageController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def send_message_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    session_repo = SQLAlchemySessionRepository(uow)
    message_repo = SQLAlchemyMessageRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = SendMessageUseCase(session_repo, message_repo, outbox)
    controller = SendMessageController(use_case)
    return TransactionalHandler(uow, controller.handle)
