from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.application.use_cases import CreateApiKeyUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.create_api_key_controller import CreateApiKeyController
from shared.infra.transactional_handler import TransactionalHandler


def create_api_key_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = CoreUnitOfWork(session_factory)
    use_case = CreateApiKeyUseCase(uow.projects, uow.api_keys, uow.outbox)
    controller = CreateApiKeyController(use_case)
    return TransactionalHandler(uow, controller.handle)
