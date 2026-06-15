from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases import ListMessagesUseCase
from modules.agent.presentation.controllers.list_messages_controller import ListMessagesController
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def list_messages_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.messages
    use_case = ListMessagesUseCase(repo)
    controller = ListMessagesController(use_case)
    return TransactionalHandler(uow, controller.handle)
