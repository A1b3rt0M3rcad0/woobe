from modules.agent.application.use_cases import GetDocumentUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.document_repositories import SQLAlchemyGuardedDocumentRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.get_document_controller import GetDocumentController
from shared.infra.transactional_handler import TransactionalHandler


def get_document_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyGuardedDocumentRepository(uow)
    use_case = GetDocumentUseCase(repo)
    controller = GetDocumentController(use_case)
    return TransactionalHandler(uow, controller.handle)
