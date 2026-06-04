from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.knowledge.infra.repositories import SQLAlchemyDocumentCollectionRepository
from modules.knowledge.presentation.controllers.get_collection_controller import GetCollectionController
from modules.knowledge.service.use_cases import GetCollectionUseCase
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def get_collection_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyDocumentCollectionRepository(uow)
    use_case = GetCollectionUseCase(repo)
    controller = GetCollectionController(use_case)
    return TransactionalHandler(uow, controller.handle)
