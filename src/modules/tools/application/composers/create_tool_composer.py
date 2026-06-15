from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.infra.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemyToolRepository
from modules.tools.application.use_cases import CreateToolUseCase
from modules.tools.presentation.controllers.create_tool_controller import CreateToolController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyToolRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateToolUseCase(repo, outbox)
    controller = CreateToolController(use_case)
    return TransactionalHandler(uow, controller.handle)
