from modules.agent.application.use_cases.environment_session_use_cases import (
    EnvironmentAwareCreateSessionUseCase,
)
from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_agent_runtime_transactions,
)
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.adapters.agent_runtime_environment_guard import (
    AgentRuntimeEnvironmentGuard,
)
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentRepositoryWithProviderModels,
)
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.runtime_session_repository import SQLAlchemyRuntimeSessionRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_session_controller import CreateSessionController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.asac_runtime_release_repository import SQLAlchemySelectedAgentReleaseRepository


def create_session_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    session_repo = SQLAlchemyRuntimeSessionRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    release_repo = SQLAlchemySelectedAgentReleaseRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    delegate = EnvironmentAwareCreateSessionUseCase(
        session_repo,
        agent_repo,
        release_repo,
        outbox,
    )
    use_case = AgentRuntimeEnvironmentGuard(
        delegate,
        build_agent_runtime_transactions(),
        default_environment="draft",
    )
    controller = CreateSessionController(use_case)
    return TransactionalHandler(uow, controller.handle)
