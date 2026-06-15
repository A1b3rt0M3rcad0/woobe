from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.presentation.controllers.get_collection_controller import GetCollectionController
from modules.agent.application.use_cases import GetCollectionUseCase
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def get_collection_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.document_collections
    use_case = GetCollectionUseCase(repo)
    controller = GetCollectionController(use_case)
    return TransactionalHandler(uow, controller.handle)
