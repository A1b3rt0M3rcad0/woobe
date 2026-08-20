from modules.agent.application.use_cases.environment_session_use_cases import (
    EnvironmentAwareCreateSessionUseCase,
)
from modules.agent.composition.resources import DATABASE_ENGINE, SESSION_FACTORY
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
    SQLAlchemyAgentRepositoryWithProviderModels,
)
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.runtime_session_repository import SQLAlchemyRuntimeSessionRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_session_controller import CreateSessionController
from modules.agent.runtime.runtime_environment_guard import AgentRuntimeEnvironmentGuard
from shared.infra.transactional_handler import TransactionalHandler


def create_session_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    session_repo = SQLAlchemyRuntimeSessionRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    delegate = EnvironmentAwareCreateSessionUseCase(
        session_repo,
        agent_repo,
        release_repo,
        outbox,
    )
    use_case = AgentRuntimeEnvironmentGuard(
        delegate,
        SESSION_FACTORY,
        default_environment="draft",
    )
    controller = CreateSessionController(use_case)
    return TransactionalHandler(uow, controller.handle)
