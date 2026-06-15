from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.infra.repositories import SQLAlchemyToolRepository
from modules.tools.application.use_cases import DeleteToolUseCase
from modules.tools.presentation.controllers.delete_tool_controller import DeleteToolController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def delete_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyToolRepository(uow)
    use_case = DeleteToolUseCase(repo)
    controller = DeleteToolController(use_case)
    return TransactionalHandler(uow, controller.handle)
