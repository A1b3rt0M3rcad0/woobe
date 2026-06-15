from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.infra.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemySecretRepository
from modules.tools.application.use_cases import CreateSecretUseCase
from modules.tools.presentation.controllers.create_secret_controller import CreateSecretController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_secret_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemySecretRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateSecretUseCase(repo, outbox)
    controller = CreateSecretController(use_case)
    return TransactionalHandler(uow, controller.handle)
