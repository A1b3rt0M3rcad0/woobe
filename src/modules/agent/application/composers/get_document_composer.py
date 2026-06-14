from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyDocumentRepository
from modules.knowledge.presentation.controllers.get_document_controller import GetDocumentController
from modules.agent.application.use_cases.knowledge_use_cases import GetDocumentUseCase
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def get_document_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyDocumentRepository(uow)
    use_case = GetDocumentUseCase(repo)
    controller = GetDocumentController(use_case)
    return TransactionalHandler(uow, controller.handle)
