from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.metering.infra.database.repositories import SQLAlchemyUsageDailyAgentRepository
from modules.metering.infra.database.unit_of_work import MeteringUnitOfWork
from modules.metering.application.use_cases import GetAgentDailyUsageUseCase
from modules.metering.presentation.controllers.get_agent_daily_usage_controller import GetAgentDailyUsageController
from shared.infra.transactional_handler import TransactionalHandler


def get_agent_daily_usage_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = MeteringUnitOfWork(session_factory)
    repo = SQLAlchemyUsageDailyAgentRepository(uow)
    use_case = GetAgentDailyUsageUseCase(repo)
    controller = GetAgentDailyUsageController(use_case)
    return TransactionalHandler(uow, controller.handle)
