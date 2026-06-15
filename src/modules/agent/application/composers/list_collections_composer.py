from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.presentation.controllers.list_collections_controller import ListCollectionsController
from modules.agent.application.use_cases import ListCollectionsUseCase
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def list_collections_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.document_collections
    use_case = ListCollectionsUseCase(repo)
    controller = ListCollectionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
