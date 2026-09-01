from modules.agent.application.use_cases import SearchChunksUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyDocumentChunkRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.search_chunks_controller import SearchChunksController
from shared.infra.transactional_handler import TransactionalHandler


def search_chunks_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyDocumentChunkRepository(uow)
    use_case = SearchChunksUseCase(repo)
    controller = SearchChunksController(use_case)
    return TransactionalHandler(uow, controller.handle)
