from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.application.use_cases.get_project_overview import (
    GetProjectOverviewUseCase,
)
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.get_project_overview_controller import (
    GetProjectOverviewController,
)
from shared.infra.transactional_handler import TransactionalHandler


def get_project_overview_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = CoreUnitOfWork(session_factory)
    use_case = GetProjectOverviewUseCase(uow.project_overview)
    controller = GetProjectOverviewController(use_case)
    return TransactionalHandler(uow, controller.handle)
