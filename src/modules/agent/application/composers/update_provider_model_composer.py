from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases import UpdateProviderModelUseCase
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.update_provider_model_controller import UpdateProviderModelController
from shared.infra.transactional_handler import TransactionalHandler


def update_provider_model_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = UpdateProviderModelUseCase(uow.provider_models, uow.provider_credentials)
    controller = UpdateProviderModelController(use_case)
    return TransactionalHandler(uow, controller.handle)
