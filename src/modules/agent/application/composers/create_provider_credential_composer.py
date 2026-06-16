from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.application.use_cases import CreateProviderCredentialUseCase
from modules.agent.presentation.controllers.create_provider_credential_controller import CreateProviderCredentialController
from shared.infra.transactional_handler import TransactionalHandler
from shared.infra.config import Settings
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def create_provider_credential_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    settings = Settings()
    uow = AgentUnitOfWork(session_factory)
    credential_repo = uow.provider_credentials
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = CreateProviderCredentialUseCase(credential_repo, outbox, encryption_key=settings.encryption_key)
    controller = CreateProviderCredentialController(use_case)
    return TransactionalHandler(uow, controller.handle)
