from __future__ import annotations

from typing import Any

from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.config.interface.unit_of_work import UnitOfWork

from modules.agent.infra.database.document_repositories import SQLAlchemyGuardedDocumentRepository
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
    SQLAlchemyAgentRepositoryWithProviderModels,
    SQLAlchemyProviderModelRepository,
)
from modules.agent.infra.database.release_activation_repository import (
    SQLAlchemyAgentReleaseActivationRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentInboxRepository,
    SQLAlchemyAgentOutboxRepository,
    SQLAlchemyAgentToolRepository,
    SQLAlchemyAgentToolSecretRepository,
    SQLAlchemyAskJobRepository,
    SQLAlchemyDocumentChunkRepository,
    SQLAlchemyDocumentCollectionRepository,
    SQLAlchemyKnowledgeVersionRepository,
    SQLAlchemyMessageRepository,
    SQLAlchemyProviderCredentialRepository,
    SQLAlchemySessionRepository,
)
from modules.agent.infra.database.vector_snapshot_repositories import SQLAlchemyVectorSnapshotRepository


class AgentUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._agents: SQLAlchemyAgentRepositoryWithProviderModels | None = None
        self._provider_credentials: SQLAlchemyProviderCredentialRepository | None = None
        self._provider_models: SQLAlchemyProviderModelRepository | None = None
        self._releases: SQLAlchemyAgentReleaseRepositoryWithProviderModels | None = None
        self._release_activations: SQLAlchemyAgentReleaseActivationRepository | None = None
        self._sessions: SQLAlchemySessionRepository | None = None
        self._messages: SQLAlchemyMessageRepository | None = None
        self._ask_jobs: SQLAlchemyAskJobRepository | None = None
        self._document_collections: SQLAlchemyDocumentCollectionRepository | None = None
        self._documents: SQLAlchemyGuardedDocumentRepository | None = None
        self._document_chunks: SQLAlchemyDocumentChunkRepository | None = None
        self._knowledge_versions: SQLAlchemyKnowledgeVersionRepository | None = None
        self._vector_snapshots: SQLAlchemyVectorSnapshotRepository | None = None
        self._tools: SQLAlchemyAgentToolRepository | None = None
        self._tool_secrets: SQLAlchemyAgentToolSecretRepository | None = None
        self._outbox: SQLAlchemyAgentOutboxRepository | None = None
        self._inbox: SQLAlchemyAgentInboxRepository | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("AgentUnitOfWork session not started")
        return self._session

    @property
    def agents(self) -> SQLAlchemyAgentRepositoryWithProviderModels:
        if self._agents is None:
            self._agents = SQLAlchemyAgentRepositoryWithProviderModels(self)
        return self._agents

    @property
    def provider_credentials(self) -> SQLAlchemyProviderCredentialRepository:
        if self._provider_credentials is None:
            self._provider_credentials = SQLAlchemyProviderCredentialRepository(self)
        return self._provider_credentials

    @property
    def provider_models(self) -> SQLAlchemyProviderModelRepository:
        if self._provider_models is None:
            self._provider_models = SQLAlchemyProviderModelRepository(self)
        return self._provider_models

    @property
    def releases(self) -> SQLAlchemyAgentReleaseRepositoryWithProviderModels:
        if self._releases is None:
            self._releases = SQLAlchemyAgentReleaseRepositoryWithProviderModels(self)
        return self._releases

    @property
    def release_activations(self) -> SQLAlchemyAgentReleaseActivationRepository:
        if self._release_activations is None:
            self._release_activations = SQLAlchemyAgentReleaseActivationRepository(self)
        return self._release_activations

    @property
    def sessions(self) -> SQLAlchemySessionRepository:
        if self._sessions is None:
            self._sessions = SQLAlchemySessionRepository(self)
        return self._sessions

    @property
    def messages(self) -> SQLAlchemyMessageRepository:
        if self._messages is None:
            self._messages = SQLAlchemyMessageRepository(self)
        return self._messages

    @property
    def ask_jobs(self) -> SQLAlchemyAskJobRepository:
        if self._ask_jobs is None:
            self._ask_jobs = SQLAlchemyAskJobRepository(self)
        return self._ask_jobs

    @property
    def document_collections(self) -> SQLAlchemyDocumentCollectionRepository:
        if self._document_collections is None:
            self._document_collections = SQLAlchemyDocumentCollectionRepository(self)
        return self._document_collections

    @property
    def documents(self) -> SQLAlchemyGuardedDocumentRepository:
        if self._documents is None:
            self._documents = SQLAlchemyGuardedDocumentRepository(self)
        return self._documents

    @property
    def document_chunks(self) -> SQLAlchemyDocumentChunkRepository:
        if self._document_chunks is None:
            self._document_chunks = SQLAlchemyDocumentChunkRepository(self)
        return self._document_chunks

    @property
    def knowledge_versions(self) -> SQLAlchemyKnowledgeVersionRepository:
        if self._knowledge_versions is None:
            self._knowledge_versions = SQLAlchemyKnowledgeVersionRepository(self)
        return self._knowledge_versions

    @property
    def vector_snapshots(self) -> SQLAlchemyVectorSnapshotRepository:
        if self._vector_snapshots is None:
            self._vector_snapshots = SQLAlchemyVectorSnapshotRepository(self)
        return self._vector_snapshots

    @property
    def outbox(self) -> SQLAlchemyAgentOutboxRepository:
        if self._outbox is None:
            self._outbox = SQLAlchemyAgentOutboxRepository(self)
        return self._outbox

    @property
    def inbox(self) -> SQLAlchemyAgentInboxRepository:
        if self._inbox is None:
            self._inbox = SQLAlchemyAgentInboxRepository(self)
        return self._inbox

    @property
    def tools(self) -> SQLAlchemyAgentToolRepository:
        if self._tools is None:
            self._tools = SQLAlchemyAgentToolRepository(self)
        return self._tools

    @property
    def tool_secrets(self) -> SQLAlchemyAgentToolSecretRepository:
        if self._tool_secrets is None:
            self._tool_secrets = SQLAlchemyAgentToolSecretRepository(self)
        return self._tool_secrets

    async def commit(self) -> None:
        if self._session is not None:
            try:
                await self._session.commit()
            except PendingRollbackError:
                await self.rollback()
                raise

    async def rollback(self) -> None:
        if self._session is not None:
            await self._session.rollback()

    async def __aenter__(self) -> "AgentUnitOfWork":
        self._session = self._session_factory()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._agents = None
        self._provider_credentials = None
        self._provider_models = None
        self._releases = None
        self._release_activations = None
        self._sessions = None
        self._messages = None
        self._ask_jobs = None
        self._document_collections = None
        self._documents = None
        self._document_chunks = None
        self._knowledge_versions = None
        self._vector_snapshots = None
        self._tools = None
        self._tool_secrets = None
        self._outbox = None
        self._inbox = None
