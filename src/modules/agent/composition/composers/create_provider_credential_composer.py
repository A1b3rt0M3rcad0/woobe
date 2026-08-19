from modules.agent.application.use_cases import CreateProviderCredentialUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyProviderCredentialRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_provider_credential_controller import CreateProviderCredentialController
from shared.infra.config import Settings
from shared.infra.transactional_handler import TransactionalHandler


def create_provider_credential_composer(
    database: AgentDatabase,
    settings: Settings,
) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = CreateProviderCredentialUseCase(
        credential_repo,
        outbox,
        encryption_key=settings.encryption_key,
    )
    controller = CreateProviderCredentialController(use_case)
    return TransactionalHandler(uow, controller.handle)
