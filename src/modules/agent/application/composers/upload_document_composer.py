from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyKnowledgeOutboxEventWriter
from modules.agent.presentation.controllers.upload_document_controller import UploadDocumentController
from modules.agent.application.use_cases import UploadDocumentUseCase
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def upload_document_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    doc_repo = uow.documents
    collection_repo = uow.document_collections
    outbox = SQLAlchemyKnowledgeOutboxEventWriter(uow)
    use_case = UploadDocumentUseCase(doc_repo, collection_repo, outbox)
    controller = UploadDocumentController(use_case)
    return TransactionalHandler(uow, controller.handle)
