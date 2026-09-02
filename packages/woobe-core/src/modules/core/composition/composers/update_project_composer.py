from modules.core.application.use_cases import UpdateProjectUseCase
from modules.core.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyProjectRepository,
)
from modules.core.presentation.controllers.update_project_controller import (
    UpdateProjectController,
)

from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def update_project_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyProjectRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = UpdateProjectUseCase(repository, outbox)
    controller = UpdateProjectController(use_case)
    return TransactionalHandler(uow, controller.handle)
