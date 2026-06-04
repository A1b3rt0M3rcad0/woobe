from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.infra.repositories import SQLAlchemyApiKeyRepository
from modules.core.service.use_cases import ListApiKeysByProjectUseCase
from modules.core.presentation.controllers.list_api_keys_controller import ListApiKeysController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_api_keys_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyApiKeyRepository(uow)
    use_case = ListApiKeysByProjectUseCase(repo)
    controller = ListApiKeysController(use_case)
    return TransactionalHandler(uow, controller.handle)
