from modules.agent.application.use_cases import ListAgentCollectionsUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyAgentCollectionRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_agent_collections_controller import ListAgentCollectionsController
from shared.infra.transactional_handler import TransactionalHandler


def list_agent_collections_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyAgentCollectionRepository(uow)
    use_case = ListAgentCollectionsUseCase(repo)
    controller = ListAgentCollectionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
