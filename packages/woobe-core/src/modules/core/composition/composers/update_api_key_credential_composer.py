from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.repositories import SQLAlchemyApiKeyRepository
from modules.core.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.core.application.use_cases import UpdateApiKeyCredentialUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.update_api_key_credential_controller import (
    UpdateApiKeyCredentialController,
)
from shared.infra.transactional_handler import TransactionalHandler


def update_api_key_credential_composer() -> TransactionalHandler:
    unit_of_work = CoreUnitOfWork(DATABASE_ENGINE)
    use_case = UpdateApiKeyCredentialUseCase(
        SQLAlchemyApiKeyRepository(unit_of_work),
        SQLAlchemyOutboxEventWriter(unit_of_work),
    )
    controller = UpdateApiKeyCredentialController(use_case)
    return TransactionalHandler(unit_of_work, controller.handle)

