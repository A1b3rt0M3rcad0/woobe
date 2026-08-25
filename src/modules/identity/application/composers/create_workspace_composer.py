from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import CreateWorkspaceUseCase
from modules.identity.presentation.controllers.create_workspace_controller import CreateWorkspaceController
from shared.infra.transactional_handler import TransactionalHandler


def create_workspace_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = CreateWorkspaceUseCase(uow.workspaces, uow.outbox)
    controller = CreateWorkspaceController(use_case)
    return TransactionalHandler(uow, controller.handle)
