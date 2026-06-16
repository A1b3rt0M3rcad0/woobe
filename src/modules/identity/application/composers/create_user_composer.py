from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import CreateUserUseCase
from modules.identity.presentation.controllers.create_user_controller import CreateUserController
from shared.infra.transactional_handler import TransactionalHandler


def create_user_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = CreateUserUseCase(uow.users, uow.outbox)
    controller = CreateUserController(use_case)
    return TransactionalHandler(uow, controller.handle)
