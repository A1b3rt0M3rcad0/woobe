from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.application.use_cases import ListToolsByAgentUseCase
from modules.tools.infra.database.unit_of_work import ToolsUnitOfWork
from modules.tools.presentation.controllers.list_tools_by_agent_controller import ListToolsByAgentController
from shared.application.transactional_handler import TransactionalHandler


def list_tools_by_agent_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = ToolsUnitOfWork(session_factory)
    use_case = ListToolsByAgentUseCase(uow.tools)
    controller = ListToolsByAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
