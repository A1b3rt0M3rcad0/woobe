from modules.agent.application.use_cases import ListMessagesUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import SQLAlchemyMessageRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_messages_controller import ListMessagesController
from shared.infra.transactional_handler import TransactionalHandler


def list_messages_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyMessageRepository(uow)
    use_case = ListMessagesUseCase(repo)
    controller = ListMessagesController(use_case)
    return TransactionalHandler(uow, controller.handle)
