from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import ListMembersUseCase
from modules.identity.presentation.controllers.list_members_controller import ListMembersController
from shared.infra.transactional_handler import TransactionalHandler


def list_members_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = ListMembersUseCase(uow.members)
    controller = ListMembersController(use_case)
    return TransactionalHandler(uow, controller.handle)
