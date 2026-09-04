from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.repositories import SQLAlchemyProjectRepository
from modules.core.application.use_cases import GetProjectByIdUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.get_project_controller import GetProjectController
from shared.infra.transactional_handler import TransactionalHandler


def get_project_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    use_case = GetProjectByIdUseCase(SQLAlchemyProjectRepository(uow))
    controller = GetProjectController(use_case)
    return TransactionalHandler(uow, controller.handle)

