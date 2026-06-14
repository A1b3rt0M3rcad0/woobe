from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.knowledge.infra.repositories import SQLAlchemyDocumentCollectionRepository, SQLAlchemyOutboxEventWriter
from modules.knowledge.presentation.controllers.create_collection_controller import CreateCollectionController
from modules.agent.application.use_cases.knowledge_use_cases import CreateCollectionUseCase
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_collection_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyDocumentCollectionRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateCollectionUseCase(repo, outbox)
    controller = CreateCollectionController(use_case)
    return TransactionalHandler(uow, controller.handle)
