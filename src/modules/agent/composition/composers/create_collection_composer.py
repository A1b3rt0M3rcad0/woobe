from modules.agent.application.use_cases import CreateCollectionUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyDocumentCollectionRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_collection_controller import CreateCollectionController
from shared.infra.transactional_handler import TransactionalHandler


def create_collection_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyDocumentCollectionRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = CreateCollectionUseCase(repo, outbox)
    controller = CreateCollectionController(use_case)
    return TransactionalHandler(uow, controller.handle)
