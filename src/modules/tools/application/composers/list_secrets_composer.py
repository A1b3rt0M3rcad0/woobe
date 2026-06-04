from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.infra.repositories import SQLAlchemySecretRepository
from modules.tools.service.use_cases import ListSecretsUseCase
from modules.tools.presentation.controllers.list_secrets_controller import ListSecretsController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_secrets_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemySecretRepository(uow)
    use_case = ListSecretsUseCase(repo)
    controller = ListSecretsController(use_case)
    return TransactionalHandler(uow, controller.handle)
