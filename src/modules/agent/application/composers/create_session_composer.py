from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.application.use_cases import CreateSessionUseCase
from modules.agent.application.use_cases.runtime_environment_guard import (
    AgentRuntimeEnvironmentGuard,
)
from modules.agent.presentation.controllers.create_session_controller import CreateSessionController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def create_session_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.sessions
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = AgentRuntimeEnvironmentGuard(
        CreateSessionUseCase(repo, outbox),
        session_factory,
        default_environment="draft",
    )
    controller = CreateSessionController(use_case)
    return TransactionalHandler(uow, controller.handle)
