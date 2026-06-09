from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import (
    SQLAlchemyAgentReleaseRepository,
    SQLAlchemyAgentRepository,
    SQLAlchemyProviderCredentialRepository,
)
from modules.knowledge.infra.repositories import (
    SQLAlchemyAgentCollectionRepository,
    SQLAlchemyDocumentChunkRepository,
)
from modules.metering.infra.repositories import SQLAlchemyUsageEventRepository
from modules.observability.infra.repositories import (
    SQLAlchemyTraceEventRepository,
    SQLAlchemyTraceRepository,
)
from modules.runtime.infra.repositories import (
    SQLAlchemyMessageRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemySessionRepository,
)
from modules.runtime.presentation.controllers.ask_agent_controller import (
    AskAgentController,
)
from modules.runtime.service.ask_use_case import AskAgentUseCase
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.config import Settings
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def ask_agent_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    settings = Settings()
    uow = PostgresUnitOfWork(session_factory)

    agent_repo = SQLAlchemyAgentRepository(uow)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    release_repo = SQLAlchemyAgentReleaseRepository(uow)
    session_repo = SQLAlchemySessionRepository(uow)
    message_repo = SQLAlchemyMessageRepository(uow)
    agent_collection_repo = SQLAlchemyAgentCollectionRepository(uow)
    chunk_repo = SQLAlchemyDocumentChunkRepository(uow)
    trace_repo = SQLAlchemyTraceRepository(uow)
    trace_event_repo = SQLAlchemyTraceEventRepository(uow)
    usage_repo = SQLAlchemyUsageEventRepository(uow)

    outbox = SQLAlchemyOutboxEventWriter(uow)

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
        release_repo=release_repo,
        encryption_key=settings.encryption_key,
    )

    controller = AskAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
