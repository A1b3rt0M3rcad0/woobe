from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemyUserRepository
from modules.identity.service.use_cases import CreateUserUseCase
from modules.identity.presentation.controllers.create_user_controller import CreateUserController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_user_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    user_repo = SQLAlchemyUserRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateUserUseCase(user_repo, outbox)
    controller = CreateUserController(use_case)
    return TransactionalHandler(uow, controller.handle)
