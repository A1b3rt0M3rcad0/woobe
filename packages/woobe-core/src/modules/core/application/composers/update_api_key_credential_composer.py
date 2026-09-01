from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.application.use_cases import UpdateApiKeyCredentialUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.update_api_key_credential_controller import (
    UpdateApiKeyCredentialController,
)
from shared.infra.transactional_handler import TransactionalHandler


def update_api_key_credential_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    unit_of_work = CoreUnitOfWork(session_factory)
    use_case = UpdateApiKeyCredentialUseCase(
        unit_of_work.api_keys,
        unit_of_work.outbox,
    )
    controller = UpdateApiKeyCredentialController(use_case)
    return TransactionalHandler(unit_of_work, controller.handle)
