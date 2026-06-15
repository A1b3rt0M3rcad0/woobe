from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import GetUserUseCase
from modules.identity.presentation.controllers.get_user_controller import GetUserController
from shared.infra.transactional_handler import TransactionalHandler


def get_user_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = GetUserUseCase(uow.users)
    controller = GetUserController(use_case)
    return TransactionalHandler(uow, controller.handle)
