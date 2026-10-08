from modules.core.application.use_cases.create_imported_environment import (
    CreateImportedEnvironmentUseCase,
)
from modules.core.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.core.infra.database.imported_environment_repository import (
    SQLAlchemyImportedEnvironmentRepository,
)
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.create_imported_environment_controller import (
    CreateImportedEnvironmentController,
)
from shared.infra.transactional_handler import TransactionalHandler


def create_imported_environment_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyImportedEnvironmentRepository(
        uow, encryption_key=SETTINGS.encryption_key
    )
    controller = CreateImportedEnvironmentController(
        CreateImportedEnvironmentUseCase(repository)
    )
    return TransactionalHandler(uow, controller.handle)
