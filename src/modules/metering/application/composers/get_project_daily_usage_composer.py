from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.metering.infra.repositories import SQLAlchemyUsageDailyProjectRepository
from modules.metering.application.use_cases import GetProjectDailyUsageUseCase
from modules.metering.presentation.controllers.get_project_daily_usage_controller import GetProjectDailyUsageController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def get_project_daily_usage_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyUsageDailyProjectRepository(uow)
    use_case = GetProjectDailyUsageUseCase(repo)
    controller = GetProjectDailyUsageController(use_case)
    return TransactionalHandler(uow, controller.handle)
