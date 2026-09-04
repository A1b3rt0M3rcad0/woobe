from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.repositories import SQLAlchemyApiKeyRepository
from modules.core.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.core.infra.database.repositories import SQLAlchemyProjectRepository
from modules.core.application.use_cases.create_runtime_api_key_use_case import (
    CreateRuntimeApiKeyUseCase,
)
from modules.core.infra.database.runtime_key_target_reader import RuntimeKeyTargetReader
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.create_runtime_api_key_controller import (
    CreateRuntimeApiKeyController,
)
from shared.infra.transactional_handler import TransactionalHandler


def create_runtime_api_key_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    use_case = CreateRuntimeApiKeyUseCase(
        SQLAlchemyProjectRepository(uow),
        RuntimeKeyTargetReader(uow),
        SQLAlchemyApiKeyRepository(uow),
        SQLAlchemyOutboxEventWriter(uow),
    )
    controller = CreateRuntimeApiKeyController(use_case)
    return TransactionalHandler(uow, controller.handle)

