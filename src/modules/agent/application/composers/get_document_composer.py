from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.presentation.controllers.get_document_controller import GetDocumentController
from modules.agent.application.use_cases import GetDocumentUseCase
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def get_document_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.documents
    use_case = GetDocumentUseCase(repo)
    controller = GetDocumentController(use_case)
    return TransactionalHandler(uow, controller.handle)
