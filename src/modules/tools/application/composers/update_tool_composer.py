from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.application.use_cases import UpdateToolUseCase
from modules.tools.infra.database.unit_of_work import ToolsUnitOfWork
from modules.tools.presentation.controllers.update_tool_controller import UpdateToolController
from shared.infra.transactional_handler import TransactionalHandler


def update_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = ToolsUnitOfWork(session_factory)
    use_case = UpdateToolUseCase(uow.tools, uow.outbox)
    controller = UpdateToolController(use_case)
    return TransactionalHandler(uow, controller.handle)
