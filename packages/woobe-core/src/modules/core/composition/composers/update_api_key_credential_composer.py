from modules.core.application.use_cases import UpdateApiKeyCredentialUseCase
from modules.core.infra.database.repositories import (
    SQLAlchemyApiKeyRepository,
    SQLAlchemyOutboxEventWriter,
)
from modules.core.presentation.controllers.update_api_key_credential_controller import (
    UpdateApiKeyCredentialController,
)

from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def update_api_key_credential_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyApiKeyRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = UpdateApiKeyCredentialUseCase(repository, outbox)
    controller = UpdateApiKeyCredentialController(use_case)
    return TransactionalHandler(uow, controller.handle)
