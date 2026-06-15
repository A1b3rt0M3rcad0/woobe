from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.application.use_cases import TestToolUseCase
from modules.tools.infra.database.unit_of_work import ToolsUnitOfWork
from modules.tools.presentation.controllers.test_tool_controller import TestToolController
from shared.application.transactional_handler import TransactionalHandler


def test_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = ToolsUnitOfWork(session_factory)
    use_case = TestToolUseCase()
    controller = TestToolController(use_case)
    return TransactionalHandler(uow, controller.handle)
