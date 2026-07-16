from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases.list_available_provider_models import ListAvailableProviderModelsUseCase
from modules.agent.infra.adapters.model_discovery import ModelDiscoveryService
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_available_provider_models_controller import ListAvailableProviderModelsController
from shared.infra.config import Settings
from shared.infra.transactional_handler import TransactionalHandler


def list_available_provider_models_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    settings = Settings.model_validate({})
    uow = AgentUnitOfWork(session_factory)
    use_case = ListAvailableProviderModelsUseCase(
        credential_repo=uow.provider_credentials,
        discovery_service=ModelDiscoveryService(),
        encryption_key=settings.encryption_key,
    )
    controller = ListAvailableProviderModelsController(use_case)
    return TransactionalHandler(uow, controller.handle)
