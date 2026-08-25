from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import ListWorkspacesUseCase
from modules.identity.presentation.controllers.list_workspaces_controller import ListWorkspacesController
from shared.infra.transactional_handler import TransactionalHandler


def list_workspaces_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = ListWorkspacesUseCase(uow.workspaces)
    controller = ListWorkspacesController(use_case)
    return TransactionalHandler(uow, controller.handle)
