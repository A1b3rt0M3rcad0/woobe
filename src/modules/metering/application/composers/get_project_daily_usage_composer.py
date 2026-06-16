from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.metering.infra.database.repositories import SQLAlchemyUsageDailyProjectRepository
from modules.metering.infra.database.unit_of_work import MeteringUnitOfWork
from modules.metering.application.use_cases import GetProjectDailyUsageUseCase
from modules.metering.presentation.controllers.get_project_daily_usage_controller import GetProjectDailyUsageController
from shared.infra.transactional_handler import TransactionalHandler


def get_project_daily_usage_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = MeteringUnitOfWork(session_factory)
    repo = SQLAlchemyUsageDailyProjectRepository(uow)
    use_case = GetProjectDailyUsageUseCase(repo)
    controller = GetProjectDailyUsageController(use_case)
    return TransactionalHandler(uow, controller.handle)
