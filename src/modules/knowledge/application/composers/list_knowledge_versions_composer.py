from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.knowledge.infra.repositories import SQLAlchemyKnowledgeVersionRepository
from modules.knowledge.presentation.controllers.list_knowledge_versions_controller import ListKnowledgeVersionsController
from modules.knowledge.service.use_cases import ListKnowledgeVersionsUseCase
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_knowledge_versions_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyKnowledgeVersionRepository(uow)
    use_case = ListKnowledgeVersionsUseCase(repo)
    controller = ListKnowledgeVersionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
