from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository
from modules.agent.application.use_cases import ListProviderCredentialsUseCase
from modules.agent.presentation.controllers.list_provider_credentials_controller import ListProviderCredentialsController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_provider_credentials_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyProviderCredentialRepository(uow)
    use_case = ListProviderCredentialsUseCase(repo)
    controller = ListProviderCredentialsController(use_case)
    return TransactionalHandler(uow, controller.handle)
