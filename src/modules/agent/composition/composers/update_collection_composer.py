from modules.agent.application.use_cases.update_collection_use_case import UpdateCollectionUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import SQLAlchemyDocumentCollectionRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.update_collection_controller import UpdateCollectionController
from shared.infra.transactional_handler import TransactionalHandler


def update_collection_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyDocumentCollectionRepository(uow)
    use_case = UpdateCollectionUseCase(repo)
    controller = UpdateCollectionController(use_case)
    return TransactionalHandler(uow, controller.handle)
