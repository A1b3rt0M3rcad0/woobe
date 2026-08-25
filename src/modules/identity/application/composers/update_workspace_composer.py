from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import UpdateWorkspaceUseCase
from modules.identity.presentation.controllers.update_workspace_controller import UpdateWorkspaceController
from shared.infra.transactional_handler import TransactionalHandler


def update_workspace_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = UpdateWorkspaceUseCase(uow.workspaces, uow.outbox)
    controller = UpdateWorkspaceController(use_case)
    return TransactionalHandler(uow, controller.handle)
