from modules.core.application.use_cases.create_runtime_api_key_use_case import (
    CreateRuntimeApiKeyUseCase,
)
from modules.core.infra.database.repositories import (
    SQLAlchemyApiKeyRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyProjectRepository,
)
from modules.core.infra.database.runtime_key_target_reader import RuntimeKeyTargetReader
from modules.core.infra.security.api_key_issuer import SharedApiKeyIssuer
from modules.core.presentation.controllers.create_runtime_api_key_controller import (
    CreateRuntimeApiKeyController,
)

from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def create_runtime_api_key_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    project_repo = SQLAlchemyProjectRepository(uow)
    target_reader = RuntimeKeyTargetReader(uow)
    api_key_repo = SQLAlchemyApiKeyRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    api_key_issuer = SharedApiKeyIssuer()
    use_case = CreateRuntimeApiKeyUseCase(
        project_repo,
        target_reader,
        api_key_repo,
        outbox,
        api_key_issuer,
    )
    controller = CreateRuntimeApiKeyController(use_case)
    return TransactionalHandler(uow, controller.handle)
