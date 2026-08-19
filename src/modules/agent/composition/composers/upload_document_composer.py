from modules.agent.application.use_cases import UploadDocumentUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.document_repositories import SQLAlchemyGuardedDocumentRepository
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyDocumentCollectionRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.upload_document_controller import UploadDocumentController
from shared.infra.transactional_handler import TransactionalHandler


def upload_document_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    doc_repo = SQLAlchemyGuardedDocumentRepository(uow)
    collection_repo = SQLAlchemyDocumentCollectionRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = UploadDocumentUseCase(doc_repo, collection_repo, outbox)
    controller = UploadDocumentController(use_case)
    return TransactionalHandler(uow, controller.handle)
