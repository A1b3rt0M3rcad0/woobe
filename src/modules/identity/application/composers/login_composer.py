from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.repositories import SQLAlchemyUserRepository
from modules.identity.application.use_cases import LoginUseCase
from modules.identity.presentation.controllers.login_controller import LoginController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def login_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyUserRepository(uow)
    use_case = LoginUseCase(repo)
    controller = LoginController(use_case)
    return TransactionalHandler(uow, controller.handle)
