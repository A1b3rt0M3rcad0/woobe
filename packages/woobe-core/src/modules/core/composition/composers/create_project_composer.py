from modules.core.application.use_cases import CreateProjectUseCase
from modules.core.infra.database.project_access_repository import (
    SQLAlchemyProjectAccessRepository,
)
from modules.core.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyProjectRepository,
)
from modules.core.presentation.controllers.create_project_controller import (
    CreateProjectController,
)

from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def create_project_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    project_repo = SQLAlchemyProjectRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    access_repo = SQLAlchemyProjectAccessRepository(uow)
    use_case = CreateProjectUseCase(project_repo, outbox, access_repo)
    controller = CreateProjectController(use_case)
    return TransactionalHandler(uow, controller.handle)
