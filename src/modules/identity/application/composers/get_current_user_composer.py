from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import GetCurrentUserUseCase
from modules.identity.presentation.controllers.get_current_user_controller import GetCurrentUserController
from shared.infra.transactional_handler import TransactionalHandler


def get_current_user_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = GetCurrentUserUseCase()
    controller = GetCurrentUserController(use_case)
    return TransactionalHandler(uow, controller.handle)
