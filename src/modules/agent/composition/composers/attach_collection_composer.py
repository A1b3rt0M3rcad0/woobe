from modules.agent.application.use_cases import AttachCollectionUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyAgentCollectionRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.attach_collection_controller import AttachCollectionController
from shared.infra.transactional_handler import TransactionalHandler


def attach_collection_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyAgentCollectionRepository(uow)
    use_case = AttachCollectionUseCase(repo)
    controller = AttachCollectionController(use_case)
    return TransactionalHandler(uow, controller.handle)
