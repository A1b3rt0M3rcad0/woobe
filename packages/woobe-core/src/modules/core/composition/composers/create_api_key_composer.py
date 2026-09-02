from modules.core.application.use_cases import CreateApiKeyUseCase
from modules.core.infra.database.repositories import (
    SQLAlchemyApiKeyRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyProjectRepository,
)
from modules.core.infra.security.api_key_issuer import SharedApiKeyIssuer
from modules.core.presentation.controllers.create_api_key_controller import (
    CreateApiKeyController,
)

from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def create_api_key_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    project_repo = SQLAlchemyProjectRepository(uow)
    api_key_repo = SQLAlchemyApiKeyRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    api_key_issuer = SharedApiKeyIssuer()
    use_case = CreateApiKeyUseCase(project_repo, api_key_repo, outbox, api_key_issuer)
    controller = CreateApiKeyController(use_case)
    return TransactionalHandler(uow, controller.handle)
