from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentModelConfigRepository
from modules.agent.application.use_cases import CreateModelConfigUseCase
from modules.agent.presentation.controllers.create_model_config_controller import CreateModelConfigController
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def create_model_config_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentModelConfigRepository(uow)
    use_case = CreateModelConfigUseCase(repo)
    controller = CreateModelConfigController(use_case)
    return TransactionalHandler(uow, controller.handle)
