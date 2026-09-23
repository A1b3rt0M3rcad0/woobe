from modules.agent.application.use_cases.update_collection_use_case import UpdateCollectionUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentCollectionRepository,
    SQLAlchemyDocumentCollectionRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.update_collection_controller import UpdateCollectionController
from shared.infra.transactional_handler import TransactionalHandler


def update_collection_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyDocumentCollectionRepository(uow)
    agent_collection_repo = SQLAlchemyAgentCollectionRepository(uow)
    use_case = UpdateCollectionUseCase(repo, agent_collection_repo)
    controller = UpdateCollectionController(use_case)
    return TransactionalHandler(uow, controller.handle)
