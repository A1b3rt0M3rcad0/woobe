from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.repositories import SQLAlchemyUserRepository
from modules.identity.application.use_cases import GetUserUseCase
from modules.identity.presentation.controllers.get_user_controller import GetUserController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def get_user_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    user_repo = SQLAlchemyUserRepository(uow)
    use_case = GetUserUseCase(user_repo)
    controller = GetUserController(use_case)
    return TransactionalHandler(uow, controller.handle)
