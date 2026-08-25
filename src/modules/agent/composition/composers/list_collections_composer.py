from modules.agent.application.use_cases import ListCollectionsUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyDocumentCollectionRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_collections_controller import ListCollectionsController
from shared.infra.transactional_handler import TransactionalHandler


def list_collections_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyDocumentCollectionRepository(uow)
    use_case = ListCollectionsUseCase(repo)
    controller = ListCollectionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
