from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases import ListProviderModelsUseCase
from modules.agent.application.use_cases.list_available_provider_models import ListAvailableProviderModelsUseCase
from modules.agent.infra.adapters.model_discovery import ModelDiscoveryContext, ModelDiscoveryService
from modules.agent.infra.adapters.openrouter_embedding_discovery import OpenRouterEmbeddingModelDiscoveryService
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_provider_models_controller import ListProviderModelsController
from shared.infra.config import Settings
from shared.infra.crypto import decrypt_secret
from shared.infra.transactional_handler import TransactionalHandler


def list_provider_models_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    settings = Settings.model_validate({})
    uow = AgentUnitOfWork(session_factory)
    use_case = ListProviderModelsUseCase(uow.provider_models, uow.provider_credentials)
    discovery_service = ModelDiscoveryService()
    embedding_discovery_service = OpenRouterEmbeddingModelDiscoveryService()

    async def discover(provider: str, api_key: str, metadata: dict):
        return await discovery_service.list_models(
            ModelDiscoveryContext(provider=provider, api_key=api_key, metadata=metadata)
        )

    async def discover_embeddings(_provider: str, api_key: str, metadata: dict):
        return await embedding_discovery_service.list_models(api_key=api_key, metadata=metadata)

    discovery_use_case = ListAvailableProviderModelsUseCase(
        credential_repo=uow.provider_credentials,
        discovery=discover,
        embedding_discovery=discover_embeddings,
        resolve_secret=lambda encrypted: decrypt_secret(encrypted, settings.encryption_key),
    )
    controller = ListProviderModelsController(use_case, discovery_use_case)
    return TransactionalHandler(uow, controller.handle)
