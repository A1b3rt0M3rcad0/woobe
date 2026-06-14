from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyDocumentChunkRepository
from modules.agent.presentation.controllers.search_chunks_controller import SearchChunksController
from modules.agent.application.use_cases.knowledge_use_cases import SearchChunksUseCase
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def search_chunks_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyDocumentChunkRepository(uow)
    use_case = SearchChunksUseCase(repo)
    controller = SearchChunksController(use_case)
    return TransactionalHandler(uow, controller.handle)
