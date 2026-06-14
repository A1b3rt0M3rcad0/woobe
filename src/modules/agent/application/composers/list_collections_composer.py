from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.knowledge.infra.repositories import SQLAlchemyDocumentCollectionRepository
from modules.knowledge.presentation.controllers.list_collections_controller import ListCollectionsController
from modules.agent.application.use_cases.knowledge_use_cases import ListCollectionsUseCase
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_collections_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyDocumentCollectionRepository(uow)
    use_case = ListCollectionsUseCase(repo)
    controller = ListCollectionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
