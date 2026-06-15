from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.infra.repositories import SQLAlchemyToolRepository
from modules.tools.application.use_cases import ExecuteToolUseCase
from modules.tools.presentation.controllers.execute_tool_controller import ExecuteToolController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def execute_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    tool_repo = SQLAlchemyToolRepository(uow)
    use_case = ExecuteToolUseCase(tool_repo=tool_repo)
    controller = ExecuteToolController(use_case)
    return TransactionalHandler(uow, controller.handle)
