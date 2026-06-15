from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentModelConfigRepository
from modules.agent.application.use_cases import ListModelConfigsUseCase
from modules.agent.presentation.controllers.list_model_configs_controller import ListModelConfigsController
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def list_model_configs_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentModelConfigRepository(uow)
    use_case = ListModelConfigsUseCase(repo)
    controller = ListModelConfigsController(use_case)
    return TransactionalHandler(uow, controller.handle)
