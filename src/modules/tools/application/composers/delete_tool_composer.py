from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.application.use_cases import DeleteToolUseCase
from modules.tools.infra.database.unit_of_work import ToolsUnitOfWork
from modules.tools.presentation.controllers.delete_tool_controller import DeleteToolController
from shared.application.transactional_handler import TransactionalHandler


def delete_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = ToolsUnitOfWork(session_factory)
    use_case = DeleteToolUseCase(uow.tools)
    controller = DeleteToolController(use_case)
    return TransactionalHandler(uow, controller.handle)
