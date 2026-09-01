from modules.agent.application.use_cases import CreateCollectionUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyDocumentCollectionRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_collection_controller import CreateCollectionController
from shared.infra.transactional_handler import TransactionalHandler


def create_collection_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyDocumentCollectionRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = CreateCollectionUseCase(repo, outbox)
    controller = CreateCollectionController(use_case)
    return TransactionalHandler(uow, controller.handle)
