from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.presentation.controllers.list_agent_sessions_controller import (
    ListAgentSessionsController,
)
from modules.agent.application.use_cases import ListAgentSessionsUseCase
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def list_agent_sessions_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)

    session_repo = uow.sessions
    message_repo = uow.messages

    use_case = ListAgentSessionsUseCase(
        session_repo=session_repo,
        message_repo=message_repo,
    )

    controller = ListAgentSessionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
