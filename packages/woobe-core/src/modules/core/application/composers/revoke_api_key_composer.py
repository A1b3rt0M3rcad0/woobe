from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.application.use_cases import RevokeApiKeyUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.revoke_api_key_controller import RevokeApiKeyController
from shared.infra.transactional_handler import TransactionalHandler


def revoke_api_key_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    unit_of_work = CoreUnitOfWork(session_factory)
    use_case = RevokeApiKeyUseCase(unit_of_work.api_keys, unit_of_work.outbox)
    controller = RevokeApiKeyController(use_case)
    return TransactionalHandler(unit_of_work, controller.handle)
