from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.knowledge.infra.repositories import SQLAlchemyDocumentRepository
from modules.knowledge.presentation.controllers.list_documents_controller import ListDocumentsController
from modules.knowledge.service.use_cases import ListDocumentsUseCase
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_documents_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyDocumentRepository(uow)
    use_case = ListDocumentsUseCase(repo, uow)
    controller = ListDocumentsController(use_case)
    return TransactionalHandler(uow, controller.handle)
