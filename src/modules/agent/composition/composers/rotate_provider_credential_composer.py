from modules.agent.application.use_cases.rotate_provider_credential_use_case import (
    RotateProviderCredentialUseCase,
)
from modules.agent.infra.adapters.model_discovery import ModelDiscoveryService
from modules.agent.infra.adapters.provider_discovery_adapters import (
    ProviderCredentialValidator,
)
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyProviderCredentialRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.rotate_provider_credential_controller import (
    RotateProviderCredentialController,
)
from shared.infra.config import Settings
from shared.infra.transactional_handler import TransactionalHandler


def rotate_provider_credential_composer(
    database: AgentDatabase,
    settings: Settings,
) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    validator = ProviderCredentialValidator(ModelDiscoveryService())
    use_case = RotateProviderCredentialUseCase(
        credential_repo=credential_repo,
        outbox=outbox,
        validate_secret=validator,
        encryption_key=settings.encryption_key,
    )
    controller = RotateProviderCredentialController(use_case)
    return TransactionalHandler(uow, controller.handle)
