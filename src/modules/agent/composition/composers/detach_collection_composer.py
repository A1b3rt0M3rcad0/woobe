from modules.agent.application.use_cases import DetachCollectionUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyAgentCollectionRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.detach_collection_controller import DetachCollectionController
from shared.infra.transactional_handler import TransactionalHandler


def detach_collection_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyAgentCollectionRepository(uow)
    use_case = DetachCollectionUseCase(repo)
    controller = DetachCollectionController(use_case)
    return TransactionalHandler(uow, controller.handle)
