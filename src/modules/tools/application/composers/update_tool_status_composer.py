from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.application.use_cases import UpdateToolStatusUseCase
from modules.tools.infra.database.unit_of_work import ToolsUnitOfWork
from modules.tools.presentation.controllers.update_tool_status_controller import UpdateToolStatusController
from shared.infra.transactional_handler import TransactionalHandler


def update_tool_status_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = ToolsUnitOfWork(session_factory)
    use_case = UpdateToolStatusUseCase(uow.tools, uow.outbox)
    controller = UpdateToolStatusController(use_case)
    return TransactionalHandler(uow, controller.handle)
