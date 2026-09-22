from modules.core.application.use_cases.get_project_runs import GetProjectRunsUseCase
from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.project_runs_reader import SQLProjectRunsReader
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.get_project_runs_controller import (
    GetProjectRunsController,
)
from shared.infra.transactional_handler import TransactionalHandler


def get_project_runs_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    use_case = GetProjectRunsUseCase(SQLProjectRunsReader(uow))
    controller = GetProjectRunsController(use_case)
    return TransactionalHandler(uow, controller.handle)
