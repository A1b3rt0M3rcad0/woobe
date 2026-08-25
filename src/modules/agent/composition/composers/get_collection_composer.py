from modules.agent.application.use_cases import GetCollectionUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyDocumentCollectionRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.get_collection_controller import GetCollectionController
from shared.infra.transactional_handler import TransactionalHandler


def get_collection_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyDocumentCollectionRepository(uow)
    use_case = GetCollectionUseCase(repo)
    controller = GetCollectionController(use_case)
    return TransactionalHandler(uow, controller.handle)
