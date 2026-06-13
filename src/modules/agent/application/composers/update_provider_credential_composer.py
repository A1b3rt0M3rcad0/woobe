from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemyProviderCredentialRepository
from modules.agent.application.use_cases.ai_use_cases import UpdateProviderCredentialUseCase
from modules.ai.presentation.controllers.update_provider_credential_controller import UpdateProviderCredentialController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.config import Settings
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def update_provider_credential_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    settings = Settings()
    uow = PostgresUnitOfWork(session_factory)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = UpdateProviderCredentialUseCase(credential_repo, outbox, encryption_key=settings.encryption_key)
    controller = UpdateProviderCredentialController(use_case)
    return TransactionalHandler(uow, controller.handle)
