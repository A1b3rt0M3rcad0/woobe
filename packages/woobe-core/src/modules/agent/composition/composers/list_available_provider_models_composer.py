from collections.abc import Callable
from modules.agent.composition.resources import SETTINGS
from modules.agent.composition.factories.agent_uow_factory import build_agent_uow
from modules.agent.application.use_cases.list_available_provider_models import ListAvailableProviderModelsUseCase
from modules.agent.infra.adapters.model_discovery import ModelDiscoveryService
from modules.agent.infra.adapters.openrouter_embedding_discovery import OpenRouterEmbeddingModelDiscoveryService
from modules.agent.infra.adapters.provider_discovery_adapters import EmbeddingModelDiscoveryAdapter, ProviderModelDiscoveryAdapter, ProviderSecretResolver
from modules.agent.infra.adapters.provider_discovery_handler import ProviderDiscoveryHandler


def list_available_provider_models_composer() -> Callable:
    """Discovery commits authorization/pins, releases SQL, then calls the provider."""
    return ProviderDiscoveryHandler(build_agent_uow,
        discovery=ProviderModelDiscoveryAdapter(ModelDiscoveryService()),
        embedding_discovery=EmbeddingModelDiscoveryAdapter(OpenRouterEmbeddingModelDiscoveryService()),
        secret_resolver=ProviderSecretResolver(SETTINGS.encryption_key),
        use_case_factory=ListAvailableProviderModelsUseCase)
