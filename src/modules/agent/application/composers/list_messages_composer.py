from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.runtime.infra.repositories import SQLAlchemyMessageRepository
from modules.agent.application.use_cases.runtime_use_cases import ListMessagesUseCase
from modules.runtime.presentation.controllers.list_messages_controller import ListMessagesController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_messages_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyMessageRepository(uow)
    use_case = ListMessagesUseCase(repo)
    controller = ListMessagesController(use_case)
    return TransactionalHandler(uow, controller.handle)
