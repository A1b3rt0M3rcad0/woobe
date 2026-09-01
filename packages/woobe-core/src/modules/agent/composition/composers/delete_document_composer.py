from modules.agent.application.use_cases import DeleteDocumentUseCase
from modules.agent.composition.resources import DATABASE_ENGINE, FILE_STORAGE
from modules.agent.infra.database.document_repositories import (
    SQLAlchemyGuardedDocumentRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyDocumentChunkRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.delete_document_controller import (
    DeleteDocumentController,
)
from shared.infra.transactional_handler import TransactionalHandler


def delete_document_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    doc_repo = SQLAlchemyGuardedDocumentRepository(uow)
    chunk_repo = SQLAlchemyDocumentChunkRepository(uow)
    use_case = DeleteDocumentUseCase(doc_repo, chunk_repo, FILE_STORAGE)
    controller = DeleteDocumentController(use_case)
    return TransactionalHandler(uow, controller.handle)
