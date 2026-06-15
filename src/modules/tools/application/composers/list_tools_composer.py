from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.application.use_cases import ListToolsUseCase
from modules.tools.infra.database.unit_of_work import ToolsUnitOfWork
from modules.tools.presentation.controllers.list_tools_controller import ListToolsController
from shared.application.transactional_handler import TransactionalHandler


def list_tools_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = ToolsUnitOfWork(session_factory)
    use_case = ListToolsUseCase(uow.tools)
    controller = ListToolsController(use_case)
    return TransactionalHandler(uow, controller.handle)
