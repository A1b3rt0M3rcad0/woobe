from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.agent.application.use_cases import UpdateProviderCredentialUseCase
from modules.agent.presentation.controllers.update_provider_credential_controller import UpdateProviderCredentialController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.config import Settings
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def update_provider_credential_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    settings = Settings()
    uow = AgentUnitOfWork(session_factory)
    credential_repo = uow.provider_credentials
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = UpdateProviderCredentialUseCase(credential_repo, outbox, encryption_key=settings.encryption_key)
    controller = UpdateProviderCredentialController(use_case)
    return TransactionalHandler(uow, controller.handle)
