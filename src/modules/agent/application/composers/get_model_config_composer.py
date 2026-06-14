from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentModelConfigRepository
from modules.agent.application.use_cases.ai_use_cases import GetModelConfigUseCase
from modules.agent.presentation.controllers.get_model_config_controller import GetModelConfigController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def get_model_config_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentModelConfigRepository(uow)
    use_case = GetModelConfigUseCase(repo)
    controller = GetModelConfigController(use_case)
    return TransactionalHandler(uow, controller.handle)
