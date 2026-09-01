from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.application.use_cases import RotateApiKeyUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.rotate_api_key_controller import RotateApiKeyController
from shared.infra.transactional_handler import TransactionalHandler


def rotate_api_key_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    unit_of_work = CoreUnitOfWork(session_factory)
    use_case = RotateApiKeyUseCase(unit_of_work.api_keys, unit_of_work.outbox)
    controller = RotateApiKeyController(use_case)
    return TransactionalHandler(unit_of_work, controller.handle)
