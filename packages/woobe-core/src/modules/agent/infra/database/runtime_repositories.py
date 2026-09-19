from __future__ import annotations

from dataclasses import dataclass

from modules.agent.infra.database.skill_repository import SQLAlchemySkillRepository

from modules.agent.infra.database.agent_run_repository import SQLAlchemyAgentRunRepository
from modules.agent.infra.database.project_access_repository import (
    SQLAlchemyProjectAccessRepository,
)
from modules.agent.infra.database.project_environment_reader import (
    SQLAlchemyProjectEnvironmentReader,
)
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
from modules.agent.infra.database.runtime_environment_reader import (
    SQLAlchemyAgentRuntimeEnvironmentReader,
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
    """Repository set sharing one Agent persistence transaction.

    This remains transitional while the long-lived runtime moves fully behind
    Application persistence ports. Transaction ownership stays in AgentUnitOfWork.
    """

    agents: SQLAlchemyAgentRepositoryWithProviderModels
    provider_credentials: SQLAlchemyProviderCredentialRepository
    provider_models: SQLAlchemyProviderModelRepository
    releases: SQLAlchemyAgentReleaseRepositoryWithProviderModels
    sessions: SQLAlchemyRuntimeSessionRepository
    messages: SQLAlchemyMessageRepository
    runs: SQLAlchemyAgentRunRepository
    project_access: SQLAlchemyProjectAccessRepository
    environment: SQLAlchemyAgentRuntimeEnvironmentReader
    project_environment: SQLAlchemyProjectEnvironmentReader
    tools: SQLAlchemyAgentToolRepository
    tool_secrets: SQLAlchemyAgentToolSecretRepository
    agent_collections: SQLAlchemyAgentCollectionRepository
    document_chunks: SQLAlchemyDocumentChunkRepository
    knowledge_versions: SQLAlchemyKnowledgeVersionRepository
    vector_snapshots: SQLAlchemyVectorSnapshotRepository
    skills: SQLAlchemySkillRepository | None = None


def build_agent_runtime_repositories(
    uow: AgentUnitOfWork,
) -> AgentRuntimeRepositories:
    return AgentRuntimeRepositories(
        agents=SQLAlchemyAgentRepositoryWithProviderModels(uow),
        provider_credentials=SQLAlchemyProviderCredentialRepository(uow),
        provider_models=SQLAlchemyProviderModelRepository(uow),
        releases=SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow),
        sessions=SQLAlchemyRuntimeSessionRepository(uow),
        messages=SQLAlchemyMessageRepository(uow),
        runs=SQLAlchemyAgentRunRepository(uow),
        project_access=SQLAlchemyProjectAccessRepository(uow),
        environment=SQLAlchemyAgentRuntimeEnvironmentReader(uow),
        project_environment=SQLAlchemyProjectEnvironmentReader(uow),
        tools=SQLAlchemyAgentToolRepository(uow),
        tool_secrets=SQLAlchemyAgentToolSecretRepository(uow),
        agent_collections=SQLAlchemyAgentCollectionRepository(uow),
        document_chunks=SQLAlchemyDocumentChunkRepository(uow),
        knowledge_versions=SQLAlchemyKnowledgeVersionRepository(uow),
        vector_snapshots=SQLAlchemyVectorSnapshotRepository(uow),
        skills=SQLAlchemySkillRepository(uow),
    )
