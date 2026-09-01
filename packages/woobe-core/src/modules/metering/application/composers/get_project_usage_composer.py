from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.metering.application.use_cases.get_project_usage import GetProjectUsageUseCase
from modules.metering.infra.database.project_usage_reader import SQLAlchemyProjectUsageReader
from modules.metering.infra.database.unit_of_work import MeteringUnitOfWork
from modules.metering.presentation.controllers.get_project_usage_controller import (
    GetProjectUsageController,
)
from shared.infra.transactional_handler import TransactionalHandler


def get_project_usage_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = MeteringUnitOfWork(session_factory)
    reader = SQLAlchemyProjectUsageReader(uow)
    use_case = GetProjectUsageUseCase(reader)
    controller = GetProjectUsageController(use_case)
    return TransactionalHandler(uow, controller.handle)
