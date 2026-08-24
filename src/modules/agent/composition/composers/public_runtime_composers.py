from modules.agent.application.use_cases import (
    CreateAskJobUseCase,
    GetPublicAskJobUseCase,
)
from modules.agent.application.use_cases.public_runtime_request_preparer import (
    PublicRuntimeRequestPreparer,
)
from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_ask_agent_handler,
)
from modules.agent.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.runtime_environment_guard import (
    build_agent_runtime_environment_guard,
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
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.presentation.controllers.public_runtime_controllers import (
    PublicCreateJobController,
    PublicGetJobController,
    PublicRunController,
)
from modules.agent.presentation.http.controllers.public_runtime_stream_controller import (
    PublicRuntimeStreamController,
)
from shared.infra.streaming_transactional_handler import (
    StreamingTransactionalHandler,
)
from shared.infra.transactional_handler import TransactionalHandler


def public_run_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    session_repo = SQLAlchemyRuntimeSessionRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    preparer = PublicRuntimeRequestPreparer(
        release_repo,
        session_repo,
        agent_repo,
    )
    controller = PublicRunController(
        build_ask_agent_handler(DATABASE_ENGINE, SETTINGS),
        preparer.prepare,
    )
    return TransactionalHandler(uow, controller.handle)


def public_stream_composer() -> StreamingTransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    session_repo = SQLAlchemyRuntimeSessionRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    preparer = PublicRuntimeRequestPreparer(
        release_repo,
        session_repo,
        agent_repo,
    )
    service = AskAgentStreamService(
        DATABASE_ENGINE,
        SETTINGS,
        LangchainLLMFactory(),
        get_http_tool_executor(),
    )
    environment_guard = build_agent_runtime_environment_guard(DATABASE_ENGINE)
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
