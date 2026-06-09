from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.knowledge.infra.repositories import SQLAlchemyKnowledgeVersionRepository
from modules.knowledge.presentation.controllers.create_knowledge_version_controller import CreateKnowledgeVersionController
from modules.knowledge.service.use_cases import CreateKnowledgeVersionUseCase
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_knowledge_version_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyKnowledgeVersionRepository(uow)
    use_case = CreateKnowledgeVersionUseCase(repo)
    controller = CreateKnowledgeVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
