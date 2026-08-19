from modules.agent.application.use_cases import ListCollectionsUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import SQLAlchemyDocumentCollectionRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_collections_controller import ListCollectionsController
from shared.infra.transactional_handler import TransactionalHandler


def list_collections_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyDocumentCollectionRepository(uow)
    use_case = ListCollectionsUseCase(repo)
    controller = ListCollectionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
