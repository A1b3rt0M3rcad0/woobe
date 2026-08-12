from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases.environment_session_use_cases import (
    EnvironmentAwareListAgentSessionsUseCase,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_agent_sessions_controller import (
    ListAgentSessionsController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_agent_sessions_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = EnvironmentAwareListAgentSessionsUseCase(uow.sessions)
    controller = ListAgentSessionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
