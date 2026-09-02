from modules.metering.application.use_cases import GetProjectDailyUsageUseCase
from modules.metering.composition.resources import DATABASE_ENGINE
from modules.metering.infra.database.repositories import SQLAlchemyUsageDailyProjectRepository
from modules.metering.infra.database.unit_of_work import MeteringUnitOfWork
from modules.metering.presentation.controllers.get_project_daily_usage_controller import (
    GetProjectDailyUsageController,
)
from shared.infra.transactional_handler import TransactionalHandler


def get_project_daily_usage_composer() -> TransactionalHandler:
    uow = MeteringUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyUsageDailyProjectRepository(uow)
    use_case = GetProjectDailyUsageUseCase(repo)
    controller = GetProjectDailyUsageController(use_case)
    return TransactionalHandler(uow, controller.handle)
