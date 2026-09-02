from modules.core.application.use_cases import ListProjectsUseCase
from modules.core.infra.database.repositories import SQLAlchemyProjectRepository
from modules.core.presentation.controllers.list_projects_controller import (
    ListProjectsController,
)

from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def list_projects_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyProjectRepository(uow)
    use_case = ListProjectsUseCase(repository)
    controller = ListProjectsController(use_case)
    return TransactionalHandler(uow, controller.handle)
