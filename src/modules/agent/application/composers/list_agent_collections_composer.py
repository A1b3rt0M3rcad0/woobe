from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.knowledge.infra.repositories import SQLAlchemyAgentCollectionRepository
from modules.knowledge.presentation.controllers.list_agent_collections_controller import ListAgentCollectionsController
from modules.agent.application.use_cases.knowledge_use_cases import ListAgentCollectionsUseCase
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_agent_collections_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentCollectionRepository(uow)
    use_case = ListAgentCollectionsUseCase(repo)
    controller = ListAgentCollectionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
