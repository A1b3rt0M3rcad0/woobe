from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import InviteUserUseCase
from modules.identity.presentation.controllers.create_invite_controller import CreateInviteController
from shared.infra.transactional_handler import TransactionalHandler


def create_invite_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = InviteUserUseCase(uow.workspaces, uow.invites, uow.outbox)
    controller = CreateInviteController(use_case)
    return TransactionalHandler(uow, controller.handle)
