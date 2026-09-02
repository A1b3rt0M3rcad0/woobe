from modules.core.application.use_cases.get_project_overview import (
    GetProjectOverviewUseCase,
)
from modules.core.infra.database.contextual_project_overview_reader import (
    ContextualProjectOverviewReader,
)
from modules.core.presentation.controllers.get_project_overview_controller import (
    GetProjectOverviewController,
)

from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def get_project_overview_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    reader = ContextualProjectOverviewReader(uow)
    use_case = GetProjectOverviewUseCase(reader)
    controller = GetProjectOverviewController(use_case)
    return TransactionalHandler(uow, controller.handle)
