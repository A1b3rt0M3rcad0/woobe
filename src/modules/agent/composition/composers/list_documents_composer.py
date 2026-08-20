from modules.agent.application.use_cases import ListDocumentsUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.document_repositories import SQLAlchemyGuardedDocumentRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_documents_controller import ListDocumentsController
from shared.infra.transactional_handler import TransactionalHandler


def list_documents_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyGuardedDocumentRepository(uow)
    use_case = ListDocumentsUseCase(repo, uow)
    controller = ListDocumentsController(use_case)
    return TransactionalHandler(uow, controller.handle)
