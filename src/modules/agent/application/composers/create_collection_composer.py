from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyKnowledgeOutboxEventWriter
from modules.agent.presentation.controllers.create_collection_controller import CreateCollectionController
from modules.agent.application.use_cases import CreateCollectionUseCase
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def create_collection_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.document_collections
    outbox = SQLAlchemyKnowledgeOutboxEventWriter(uow)
    use_case = CreateCollectionUseCase(repo, outbox)
    controller = CreateCollectionController(use_case)
    return TransactionalHandler(uow, controller.handle)
