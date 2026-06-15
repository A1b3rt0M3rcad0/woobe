from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentReleaseRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentCollectionRepository,
)
from modules.metering.infra.repositories import SQLAlchemyUsageEventRepository
from modules.observability.infra.repositories import (
    SQLAlchemyTraceEventRepository,
    SQLAlchemyTraceRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyRuntimeOutboxEventWriter,
)
from modules.agent.presentation.controllers.ask_agent_controller import (
    AskAgentController,
)
from modules.agent.application.use_cases.ask_use_case import AskAgentUseCase
from modules.tools.infra.repositories import SQLAlchemyToolRepository
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
    trace_repo = SQLAlchemyTraceRepository(uow)
    trace_event_repo = SQLAlchemyTraceEventRepository(uow)
    usage_repo = SQLAlchemyUsageEventRepository(uow)
    tool_repo = SQLAlchemyToolRepository(uow)

    outbox = SQLAlchemyRuntimeOutboxEventWriter(uow)

    use_case = AskAgentUseCase(
        agent_repo=agent_repo,
        credential_repo=credential_repo,
        session_repo=session_repo,
        message_repo=message_repo,
        agent_collection_repo=agent_collection_repo,
        chunk_repo=chunk_repo,
        trace_repo=trace_repo,
        trace_event_repo=trace_event_repo,
        usage_repo=usage_repo,
        outbox=outbox,
        tool_repo=tool_repo,
        release_repo=release_repo,
        encryption_key=settings.encryption_key,
    )

    controller = AskAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
