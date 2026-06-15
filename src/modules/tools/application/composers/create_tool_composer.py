from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.application.use_cases import CreateToolUseCase
from modules.tools.infra.database.unit_of_work import ToolsUnitOfWork
from modules.tools.presentation.controllers.create_tool_controller import CreateToolController
from shared.application.transactional_handler import TransactionalHandler


def create_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = ToolsUnitOfWork(session_factory)
    use_case = CreateToolUseCase(uow.tools, uow.outbox)
    controller = CreateToolController(use_case)
    return TransactionalHandler(uow, controller.handle)
