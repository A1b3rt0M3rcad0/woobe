from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.core.infra.database.repositories import SQLAlchemyProjectRepository
from modules.core.application.use_cases import CreateProjectUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.create_project_controller import CreateProjectController
from shared.infra.transactional_handler import TransactionalHandler


def create_project_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    use_case = CreateProjectUseCase(SQLAlchemyProjectRepository(uow), SQLAlchemyOutboxEventWriter(uow))
    controller = CreateProjectController(use_case)
    return TransactionalHandler(uow, controller.handle)
