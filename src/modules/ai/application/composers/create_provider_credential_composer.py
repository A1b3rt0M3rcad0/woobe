from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemyProviderCredentialRepository
from modules.ai.service.use_cases import CreateProviderCredentialUseCase
from modules.ai.presentation.controllers.create_provider_credential_controller import CreateProviderCredentialController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.config import Settings
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_provider_credential_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    settings = Settings()
    uow = PostgresUnitOfWork(session_factory)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateProviderCredentialUseCase(credential_repo, outbox, encryption_key=settings.encryption_key)
    controller = CreateProviderCredentialController(use_case)
    return TransactionalHandler(uow, controller.handle)
