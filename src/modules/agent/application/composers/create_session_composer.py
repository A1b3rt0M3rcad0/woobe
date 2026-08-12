from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases.environment_session_use_cases import (
    EnvironmentAwareCreateSessionUseCase,
)
from modules.agent.application.use_cases.runtime_environment_guard import (
    AgentRuntimeEnvironmentGuard,
)
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_session_controller import CreateSessionController
from shared.infra.transactional_handler import TransactionalHandler


def create_session_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    delegate = EnvironmentAwareCreateSessionUseCase(
        uow.sessions,
        uow.agents,
        uow.releases,
        outbox,
    )
    use_case = AgentRuntimeEnvironmentGuard(
        delegate,
        session_factory,
        default_environment="draft",
    )
    controller = CreateSessionController(use_case)
    return TransactionalHandler(uow, controller.handle)
