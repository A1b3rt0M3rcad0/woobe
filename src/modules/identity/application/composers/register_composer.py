from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import RegisterUseCase
from modules.identity.presentation.controllers.register_controller import RegisterController
from shared.infra.transactional_handler import TransactionalHandler


def register_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = IdentityUnitOfWork(session_factory)
    use_case = RegisterUseCase(uow.users, uow.workspaces, uow.members, uow.outbox)
    controller = RegisterController(use_case)
    return TransactionalHandler(uow, controller.handle)
