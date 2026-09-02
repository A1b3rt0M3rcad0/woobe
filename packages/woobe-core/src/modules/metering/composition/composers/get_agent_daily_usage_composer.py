from modules.metering.application.use_cases import GetAgentDailyUsageUseCase
from modules.metering.composition.resources import DATABASE_ENGINE
from modules.metering.infra.database.repositories import SQLAlchemyUsageDailyAgentRepository
from modules.metering.infra.database.unit_of_work import MeteringUnitOfWork
from modules.metering.presentation.controllers.get_agent_daily_usage_controller import (
    GetAgentDailyUsageController,
)
from shared.infra.transactional_handler import TransactionalHandler


def get_agent_daily_usage_composer() -> TransactionalHandler:
    uow = MeteringUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyUsageDailyAgentRepository(uow)
    use_case = GetAgentDailyUsageUseCase(repo)
    controller = GetAgentDailyUsageController(use_case)
    return TransactionalHandler(uow, controller.handle)
