from modules.agent.application.use_cases import (
    CreateAskJobUseCase,
    GetPublicAskJobUseCase,
)
from modules.agent.application.use_cases.public_runtime_request_preparer import (
    PublicRuntimeRequestPreparer,
)
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.composition.workflows.public_runtime_workflows import (
    public_run_composer,
    public_stream_composer,
)
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
    SQLAlchemyAgentRepositoryWithProviderModels,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyAskJobRepository,
)
from modules.agent.infra.database.runtime_session_repository import (
    SQLAlchemyRuntimeSessionRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.public_runtime_controllers import (
    PublicCreateJobController,
    PublicGetJobController,
)
from shared.infra.transactional_handler import TransactionalHandler


def public_create_job_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    ask_job_repo = SQLAlchemyAskJobRepository(uow)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    session_repo = SQLAlchemyRuntimeSessionRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = CreateAskJobUseCase(ask_job_repo, outbox)
    preparer = PublicRuntimeRequestPreparer(
        release_repo,
        session_repo,
        agent_repo,
    )
    controller = PublicCreateJobController(use_case, preparer.prepare)
    return TransactionalHandler(uow, controller.handle)


def public_get_job_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    ask_job_repo = SQLAlchemyAskJobRepository(uow)
    use_case = GetPublicAskJobUseCase(ask_job_repo)
    controller = PublicGetJobController(use_case)
    return TransactionalHandler(uow, controller.handle)


__all__ = [
    "public_create_job_composer",
    "public_get_job_composer",
    "public_run_composer",
    "public_stream_composer",
]
