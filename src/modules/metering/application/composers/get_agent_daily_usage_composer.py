from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.metering.infra.repositories import SQLAlchemyUsageDailyAgentRepository
from modules.metering.application.use_cases import GetAgentDailyUsageUseCase
from modules.metering.presentation.controllers.get_agent_daily_usage_controller import GetAgentDailyUsageController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def get_agent_daily_usage_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyUsageDailyAgentRepository(uow)
    use_case = GetAgentDailyUsageUseCase(repo)
    controller = GetAgentDailyUsageController(use_case)
    return TransactionalHandler(uow, controller.handle)
