from modules.agent.application.use_cases import ListProviderModelsUseCase
from modules.agent.application.use_cases.list_available_provider_models import (
    ListAvailableProviderModelsUseCase,
)
from modules.agent.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.agent.infra.adapters.model_discovery import ModelDiscoveryService
from modules.agent.infra.adapters.openrouter_embedding_discovery import (
    OpenRouterEmbeddingModelDiscoveryService,
)
from modules.agent.infra.adapters.provider_discovery_adapters import (
    EmbeddingModelDiscoveryAdapter,
    ProviderModelDiscoveryAdapter,
    ProviderSecretResolver,
)
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyProviderModelRepository,
)
from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_provider_models_controller import (
    ListProviderModelsController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_provider_models_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    provider_model_repo = SQLAlchemyProviderModelRepository(uow)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    use_case = ListProviderModelsUseCase(provider_model_repo, credential_repo)
    discovery = ProviderModelDiscoveryAdapter(ModelDiscoveryService())
    embedding_discovery = EmbeddingModelDiscoveryAdapter(
        OpenRouterEmbeddingModelDiscoveryService()
    )
    secret_resolver = ProviderSecretResolver(SETTINGS.encryption_key)
    discovery_use_case = ListAvailableProviderModelsUseCase(
        credential_repo=credential_repo,
        discovery=discovery,
        embedding_discovery=embedding_discovery,
        resolve_secret=secret_resolver,
    )
    controller = ListProviderModelsController(use_case, discovery_use_case)
    return TransactionalHandler(uow, controller.handle)
