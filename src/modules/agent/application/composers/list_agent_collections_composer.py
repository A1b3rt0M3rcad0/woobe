from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentCollectionRepository
from modules.agent.presentation.controllers.list_agent_collections_controller import ListAgentCollectionsController
from modules.agent.application.use_cases import ListAgentCollectionsUseCase
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def list_agent_collections_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentCollectionRepository(uow)
    use_case = ListAgentCollectionsUseCase(repo)
    controller = ListAgentCollectionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
