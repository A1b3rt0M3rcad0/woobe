from modules.agent.application.use_cases import SendMessageUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyMessageRepository,
)
from modules.agent.infra.database.runtime_session_repository import SQLAlchemyRuntimeSessionRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.send_message_controller import SendMessageController
from shared.infra.transactional_handler import TransactionalHandler


def send_message_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    session_repo = SQLAlchemyRuntimeSessionRepository(uow)
    message_repo = SQLAlchemyMessageRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = SendMessageUseCase(session_repo, message_repo, outbox)
    controller = SendMessageController(use_case)
    return TransactionalHandler(uow, controller.handle)
