from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases.provider_management_cases import ArchiveProviderModelUseCase, ProviderModelUsageUseCase
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.model_lifecycle_controller import ModelLifecycleController
from shared.infra.transactional_handler import TransactionalHandler


def model_lifecycle_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    usage = ProviderModelUsageUseCase(uow.provider_models, uow.agents, uow.releases)
    use_case = ArchiveProviderModelUseCase(uow.provider_models, usage)
    controller = ModelLifecycleController(use_case)
    return TransactionalHandler(uow, controller.handle)
