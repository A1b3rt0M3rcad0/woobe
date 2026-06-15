from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.application.use_cases import ExecuteToolUseCase
from modules.tools.infra.database.unit_of_work import ToolsUnitOfWork
from modules.tools.presentation.controllers.execute_tool_controller import ExecuteToolController
from shared.infra.transactional_handler import TransactionalHandler


def execute_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = ToolsUnitOfWork(session_factory)
    use_case = ExecuteToolUseCase(tool_repo=uow.tools)
    controller = ExecuteToolController(use_case)
    return TransactionalHandler(uow, controller.handle)
