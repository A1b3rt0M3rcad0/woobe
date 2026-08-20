from __future__ import annotations

from dataclasses import dataclass

from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
    SQLAlchemyAgentRepositoryWithProviderModels,
    SQLAlchemyProviderModelRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentCollectionRepository,
    SQLAlchemyAgentToolRepository,
    SQLAlchemyAgentToolSecretRepository,
    SQLAlchemyDocumentChunkRepository,
    SQLAlchemyKnowledgeVersionRepository,
    SQLAlchemyMessageRepository,
    SQLAlchemyProviderCredentialRepository,
)
from modules.agent.infra.database.runtime_session_repository import (
    SQLAlchemyRuntimeSessionRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.vector_snapshot_repositories import (
    SQLAlchemyVectorSnapshotRepository,
)


@dataclass(frozen=True, slots=True)
class AgentRuntimeRepositories:
    """Explicit repository set for one Agent runtime transaction.

    The UnitOfWork owns only transaction/session lifecycle. Runtime phases receive
    this fixed dependency set instead of resolving repositories from the UoW.
    """

    transaction: AgentUnitOfWork
    agents: SQLAlchemyAgentRepositoryWithProviderModels
    provider_credentials: SQLAlchemyProviderCredentialRepository
    provider_models: SQLAlchemyProviderModelRepository
    releases: SQLAlchemyAgentReleaseRepositoryWithProviderModels
    sessions: SQLAlchemyRuntimeSessionRepository
    messages: SQLAlchemyMessageRepository
    tools: SQLAlchemyAgentToolRepository
    tool_secrets: SQLAlchemyAgentToolSecretRepository
    agent_collections: SQLAlchemyAgentCollectionRepository
    document_chunks: SQLAlchemyDocumentChunkRepository
    knowledge_versions: SQLAlchemyKnowledgeVersionRepository
    vector_snapshots: SQLAlchemyVectorSnapshotRepository

    async def commit(self) -> None:
        await self.transaction.commit()


def build_agent_runtime_repositories(
    uow: AgentUnitOfWork,
) -> AgentRuntimeRepositories:
    return AgentRuntimeRepositories(
        transaction=uow,
        agents=SQLAlchemyAgentRepositoryWithProviderModels(uow),
        provider_credentials=SQLAlchemyProviderCredentialRepository(uow),
        provider_models=SQLAlchemyProviderModelRepository(uow),
        releases=SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow),
        sessions=SQLAlchemyRuntimeSessionRepository(uow),
        messages=SQLAlchemyMessageRepository(uow),
        tools=SQLAlchemyAgentToolRepository(uow),
        tool_secrets=SQLAlchemyAgentToolSecretRepository(uow),
        agent_collections=SQLAlchemyAgentCollectionRepository(uow),
        document_chunks=SQLAlchemyDocumentChunkRepository(uow),
        knowledge_versions=SQLAlchemyKnowledgeVersionRepository(uow),
        vector_snapshots=SQLAlchemyVectorSnapshotRepository(uow),
    )
