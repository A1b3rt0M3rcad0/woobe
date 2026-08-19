from modules.agent.application.use_cases.list_available_provider_models import (
    ListAvailableProviderModelsUseCase,
)
from modules.agent.infra.adapters.model_discovery import ModelDiscoveryService
from modules.agent.infra.adapters.openrouter_embedding_discovery import (
    OpenRouterEmbeddingModelDiscoveryService,
)
from modules.agent.infra.adapters.provider_discovery_adapters import (
    EmbeddingModelDiscoveryAdapter,
    ProviderModelDiscoveryAdapter,
    ProviderSecretResolver,
)
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_available_provider_models_controller import (
    ListAvailableProviderModelsController,
)
from shared.infra.config import Settings
from shared.infra.transactional_handler import TransactionalHandler


def list_available_provider_models_composer(
    database: AgentDatabase,
    settings: Settings,
) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    discovery = ProviderModelDiscoveryAdapter(ModelDiscoveryService())
    embedding_discovery = EmbeddingModelDiscoveryAdapter(
        OpenRouterEmbeddingModelDiscoveryService()
    )
    secret_resolver = ProviderSecretResolver(settings.encryption_key)
    use_case = ListAvailableProviderModelsUseCase(
        credential_repo=credential_repo,
        discovery=discovery,
        embedding_discovery=embedding_discovery,
        resolve_secret=secret_resolver,
    )
    controller = ListAvailableProviderModelsController(use_case)
    return TransactionalHandler(uow, controller.handle)
