from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases import CreateProviderModelUseCase
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_provider_model_controller import CreateProviderModelController
from shared.infra.transactional_handler import TransactionalHandler


def create_provider_model_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = CreateProviderModelUseCase(uow.provider_models, uow.provider_credentials)
    controller = CreateProviderModelController(use_case)
    return TransactionalHandler(uow, controller.handle)
