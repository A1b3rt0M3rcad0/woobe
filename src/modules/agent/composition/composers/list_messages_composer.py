from modules.agent.application.use_cases import ListMessagesUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyMessageRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_messages_controller import ListMessagesController
from shared.infra.transactional_handler import TransactionalHandler


def list_messages_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyMessageRepository(uow)
    use_case = ListMessagesUseCase(repo)
    controller = ListMessagesController(use_case)
    return TransactionalHandler(uow, controller.handle)
