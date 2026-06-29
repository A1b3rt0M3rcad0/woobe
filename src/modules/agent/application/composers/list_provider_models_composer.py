from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases import ListProviderModelsUseCase
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_provider_models_controller import ListProviderModelsController
from shared.infra.transactional_handler import TransactionalHandler


def list_provider_models_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = ListProviderModelsUseCase(uow.provider_models, uow.provider_credentials)
    controller = ListProviderModelsController(use_case)
    return TransactionalHandler(uow, controller.handle)
