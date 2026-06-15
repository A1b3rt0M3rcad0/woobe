from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import LoginUseCase
from modules.identity.presentation.controllers.login_controller import LoginController
from shared.infra.transactional_handler import TransactionalHandler


def login_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = LoginUseCase(uow.users)
    controller = LoginController(use_case)
    return TransactionalHandler(uow, controller.handle)
