from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import AddMemberToWorkspaceUseCase
from modules.identity.presentation.controllers.add_member_controller import AddMemberController
from shared.infra.transactional_handler import TransactionalHandler


def add_member_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = AddMemberToWorkspaceUseCase(uow.workspaces, uow.users, uow.members, uow.outbox)
    controller = AddMemberController(use_case)
    return TransactionalHandler(uow, controller.handle)
