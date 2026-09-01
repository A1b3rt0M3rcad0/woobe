from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import ListInvitesUseCase
from modules.identity.presentation.controllers.list_invites_controller import ListInvitesController
from shared.infra.transactional_handler import TransactionalHandler


def list_invites_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = ListInvitesUseCase(uow.invites)
    controller = ListInvitesController(use_case)
    return TransactionalHandler(uow, controller.handle)
