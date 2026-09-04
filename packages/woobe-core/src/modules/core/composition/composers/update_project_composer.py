from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.core.infra.database.repositories import SQLAlchemyProjectRepository
from modules.core.application.use_cases import UpdateProjectUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.update_project_controller import UpdateProjectController
from shared.infra.transactional_handler import TransactionalHandler


def update_project_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    use_case = UpdateProjectUseCase(SQLAlchemyProjectRepository(uow), SQLAlchemyOutboxEventWriter(uow))
    controller = UpdateProjectController(use_case)
    return TransactionalHandler(uow, controller.handle)
