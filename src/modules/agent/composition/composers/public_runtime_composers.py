from modules.agent.application.use_cases import CreateAskJobUseCase
from modules.agent.application.use_cases.public_runtime_request_preparer import (
    PublicRuntimeRequestPreparer,
)
from modules.agent.composition.runtime.ask_agent_runtime_factory import (
    build_ask_agent_handler,
)
from modules.agent.composition.runtime.ask_agent_stream_service import (
    AskAgentStreamService,
)
from modules.agent.composition.runtime.environment_guard import (
    build_agent_runtime_environment_guard,
)
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.database.database import AgentDatabase, agent_session_factory
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
    PublicRunController,
)
from modules.agent.presentation.controllers.public_runtime_stream_controller import (
    PublicRuntimeStreamController,
)
from shared.infra.config import Settings
from shared.infra.streaming_transactional_handler import (
    StreamingTransactionalHandler,
)
from shared.infra.transactional_handler import TransactionalHandler


def public_run_composer(
    database: AgentDatabase,
    settings: Settings,
) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    session_repo = SQLAlchemyRuntimeSessionRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    preparer = PublicRuntimeRequestPreparer(
        release_repo,
        session_repo,
        agent_repo,
    )
    controller = PublicRunController(
        build_ask_agent_handler(database, settings),
        preparer.prepare,
    )
    return TransactionalHandler(uow, controller.handle)


def public_stream_composer(
    database: AgentDatabase,
    settings: Settings,
) -> StreamingTransactionalHandler:
    uow = AgentUnitOfWork(database)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    session_repo = SQLAlchemyRuntimeSessionRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    preparer = PublicRuntimeRequestPreparer(
        release_repo,
        session_repo,
        agent_repo,
    )
    service = AskAgentStreamService(
        database,
        settings,
        LangchainLLMFactory(),
        get_http_tool_executor(),
    )
    environment_guard = build_agent_runtime_environment_guard(
        agent_session_factory(database)
    )
    controller = PublicRuntimeStreamController(
        service,
        preparer.prepare,
        environment_guard,
    )
    return StreamingTransactionalHandler(
        uow,
        controller.handle,
        keep_uow_open_for_stream=False,
    )


def public_create_job_composer(
    database: AgentDatabase,
) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
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


def public_get_job_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    ask_job_repo = SQLAlchemyAskJobRepository(uow)
    controller = PublicGetJobController(ask_job_repo)
    return TransactionalHandler(uow, controller.handle)
