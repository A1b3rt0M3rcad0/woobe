from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.application.use_cases import ListApiKeysByProjectUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.list_api_keys_controller import ListApiKeysController
from shared.infra.transactional_handler import TransactionalHandler


def list_api_keys_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = CoreUnitOfWork(session_factory)
    use_case = ListApiKeysByProjectUseCase(uow.api_keys)
    controller = ListApiKeysController(use_case)
    return TransactionalHandler(uow, controller.handle)
