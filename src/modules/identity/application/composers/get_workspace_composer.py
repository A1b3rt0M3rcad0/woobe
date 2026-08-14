from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import GetWorkspaceUseCase
from modules.identity.presentation.controllers.get_workspace_controller import GetWorkspaceController
from shared.infra.transactional_handler import TransactionalHandler


def get_workspace_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = GetWorkspaceUseCase(uow.workspaces)
    controller = GetWorkspaceController(use_case)
    return TransactionalHandler(uow, controller.handle)
