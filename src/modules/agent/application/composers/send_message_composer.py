from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyRuntimeOutboxEventWriter
from modules.agent.application.use_cases import SendMessageUseCase
from modules.agent.presentation.controllers.send_message_controller import SendMessageController
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def send_message_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    session_repo = uow.sessions
    message_repo = uow.messages
    outbox = SQLAlchemyRuntimeOutboxEventWriter(uow)
    use_case = SendMessageUseCase(session_repo, message_repo, outbox)
    controller = SendMessageController(use_case)
    return TransactionalHandler(uow, controller.handle)
