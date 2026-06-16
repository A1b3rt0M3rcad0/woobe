from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentReleaseRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentCollectionRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
)
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.metering_usage_recorder import MeteringUsageRecorder
from modules.agent.infra.adapters.observability_trace_recorder import ObservabilityTraceRecorder
from modules.agent.infra.adapters.tools_tool_executor import ToolsToolExecutor
from modules.agent.infra.adapters.tools_tool_repository import ToolsToolRepository
from modules.agent.presentation.controllers.ask_agent_controller import (
    AskAgentController,
)
from modules.agent.application.use_cases.ask_use_case import AskAgentUseCase
from shared.infra.transactional_handler import TransactionalHandler
from shared.infra.config import Settings
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def ask_agent_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    settings = Settings()
    uow = AgentUnitOfWork(session_factory)

    agent_repo = uow.agents
    credential_repo = uow.provider_credentials
    release_repo = SQLAlchemyAgentReleaseRepository(uow)
    session_repo = uow.sessions
    message_repo = uow.messages
    agent_collection_repo = SQLAlchemyAgentCollectionRepository(uow)
    chunk_repo = uow.document_chunks
    tool_repo = ToolsToolRepository(uow)

    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    trace_recorder = ObservabilityTraceRecorder(uow)
    usage_recorder = MeteringUsageRecorder(uow)
    tool_executor = ToolsToolExecutor(tool_repo)
    llm_factory = LangchainLLMFactory()

    use_case = AskAgentUseCase(
        agent_repo=agent_repo,
        credential_repo=credential_repo,
        session_repo=session_repo,
        message_repo=message_repo,
        agent_collection_repo=agent_collection_repo,
        chunk_repo=chunk_repo,
        trace_recorder=trace_recorder,
        usage_recorder=usage_recorder,
        outbox=outbox,
        llm_factory=llm_factory,
        tool_executor=tool_executor,
        tool_repo=tool_repo,
        release_repo=release_repo,
        encryption_key=settings.encryption_key,
    )

    controller = AskAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
