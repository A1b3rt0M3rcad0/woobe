from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.knowledge.infra.repositories import SQLAlchemyDocumentCollectionRepository, SQLAlchemyDocumentRepository, SQLAlchemyOutboxEventWriter
from modules.knowledge.presentation.controllers.upload_document_controller import UploadDocumentController
from modules.agent.application.use_cases.knowledge_use_cases import UploadDocumentUseCase
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def upload_document_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    doc_repo = SQLAlchemyDocumentRepository(uow)
    collection_repo = SQLAlchemyDocumentCollectionRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = UploadDocumentUseCase(doc_repo, collection_repo, outbox)
    controller = UploadDocumentController(use_case)
    return TransactionalHandler(uow, controller.handle)
