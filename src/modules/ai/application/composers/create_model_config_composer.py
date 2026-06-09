from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import SQLAlchemyAgentModelConfigRepository
from modules.ai.service.use_cases import CreateModelConfigUseCase
from modules.ai.presentation.controllers.create_model_config_controller import CreateModelConfigController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_model_config_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentModelConfigRepository(uow)
    use_case = CreateModelConfigUseCase(repo)
    controller = CreateModelConfigController(use_case)
    return TransactionalHandler(uow, controller.handle)
