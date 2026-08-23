from modules.agent.application.use_cases import UploadDocumentFileUseCase
from modules.agent.composition.resources import DATABASE_ENGINE, FILE_STORAGE, SETTINGS
from modules.agent.infra.database.document_repositories import (
    SQLAlchemyGuardedDocumentRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyDocumentCollectionRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.upload_document_file_controller import (
    UploadDocumentFileController,
)
from shared.infra.transactional_handler import TransactionalHandler


def upload_document_file_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    doc_repo = SQLAlchemyGuardedDocumentRepository(uow)
    collection_repo = SQLAlchemyDocumentCollectionRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = UploadDocumentFileUseCase(
        doc_repo,
        collection_repo,
        outbox,
        FILE_STORAGE,
        SETTINGS,
    )
    controller = UploadDocumentFileController(use_case)
    return TransactionalHandler(uow, controller.handle)
