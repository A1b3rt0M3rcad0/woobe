from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.presentation.controllers.search_chunks_controller import SearchChunksController
from modules.agent.application.use_cases import SearchChunksUseCase
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def search_chunks_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.document_chunks
    use_case = SearchChunksUseCase(repo)
    controller = SearchChunksController(use_case)
    return TransactionalHandler(uow, controller.handle)
