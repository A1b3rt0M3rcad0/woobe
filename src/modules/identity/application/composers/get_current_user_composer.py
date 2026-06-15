from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.application.use_cases import GetCurrentUserUseCase
from modules.identity.presentation.controllers.get_current_user_controller import GetCurrentUserController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def get_current_user_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    use_case = GetCurrentUserUseCase()
    controller = GetCurrentUserController(use_case)
    return TransactionalHandler(uow, controller.handle)
