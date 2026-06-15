from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.infra.repositories import SQLAlchemyApiKeyRepository, SQLAlchemyOutboxEventWriter, SQLAlchemyProjectRepository
from modules.core.application.use_cases import CreateApiKeyUseCase
from modules.core.presentation.controllers.create_api_key_controller import CreateApiKeyController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_api_key_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    project_repo = SQLAlchemyProjectRepository(uow)
    api_key_repo = SQLAlchemyApiKeyRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateApiKeyUseCase(project_repo, api_key_repo, outbox)
    controller = CreateApiKeyController(use_case)
    return TransactionalHandler(uow, controller.handle)
