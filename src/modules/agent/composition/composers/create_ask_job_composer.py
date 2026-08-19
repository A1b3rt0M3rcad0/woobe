from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.presentation.controllers.create_ask_job_controller import (
    CreateAskJobController,
)
from modules.agent.application.use_cases import CreateAskJobUseCase
from modules.agent.application.use_cases.runtime_environment_guard import (
    AgentRuntimeEnvironmentGuard,
)
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def create_ask_job_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.ask_jobs
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = AgentRuntimeEnvironmentGuard(
        CreateAskJobUseCase(repo, outbox),
        session_factory,
        default_environment="production",
    )
    controller = CreateAskJobController(use_case)
    return TransactionalHandler(uow, controller.handle)
