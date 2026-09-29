from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from modules.agent.domain.entities import (
    Agent,
    AgentCollection,
    AgentContract,
    AgentModelConfig,
    AgentPrompt,
    AgentRelease,
    AgentReleaseTest,
    AskJob,
    Document,
    DocumentChunk,
    DocumentCollection,
    KnowledgeVersion,
    Message,
    ProviderCredential,
    Secret,
    Session,
    Tool,
)
from modules.agent.domain.enums import ReleaseStatus
from shared.contracts.pagination import CursorPage


class ProviderCredentialRepository(ABC):

    @abstractmethod
    async def save(
        self, credential: ProviderCredential
    ) -> ProviderCredential: ...

    @abstractmethod
    async def get_by_id(self, credential_id: UUID) -> ProviderCredential | None: ...

    @abstractmethod
    async def list_by_project(
        self, project_id: UUID
    ) -> list[ProviderCredential]: ...

    @abstractmethod
    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[ProviderCredential]: ...

    @abstractmethod
    async def update(
        self, credential: ProviderCredential
    ) -> ProviderCredential: ...

    @abstractmethod
    async def delete(self, credential_id: UUID) -> None: ...


class AgentRepository(ABC):

    @abstractmethod
    async def save(self, agent: Agent) -> Agent: ...

    @abstractmethod
    async def get_by_id(self, agent_id: UUID) -> Agent | None: ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[Agent]: ...

    @abstractmethod
    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Agent]: ...

    @abstractmethod
    async def update(self, agent: Agent) -> Agent: ...

    @abstractmethod
    async def delete(self, agent_id: UUID) -> None: ...


class AgentPromptRepository(ABC):

    @abstractmethod
    async def save(self, prompt: AgentPrompt) -> AgentPrompt: ...

    @abstractmethod
    async def get_by_id(self, prompt_id: UUID) -> AgentPrompt | None: ...

    @abstractmethod
    async def get_by_version(
        self, agent_id: UUID, version: str
    ) -> AgentPrompt | None: ...

    @abstractmethod
    async def list_by_agent(
        self, agent_id: UUID
    ) -> list[AgentPrompt]: ...

    @abstractmethod
    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentPrompt]: ...


class AgentContractRepository(ABC):

    @abstractmethod
    async def save(self, contract: AgentContract) -> AgentContract: ...

    @abstractmethod
    async def get_by_id(self, contract_id: UUID) -> AgentContract | None: ...

    @abstractmethod
    async def get_by_version(
        self, agent_id: UUID, version: str
    ) -> AgentContract | None: ...

    @abstractmethod
    async def list_by_agent(
        self, agent_id: UUID
    ) -> list[AgentContract]: ...

    @abstractmethod
    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentContract]: ...

    @abstractmethod
    async def delete(self, contract_id: UUID) -> None: ...


class AgentModelConfigRepository(ABC):

    @abstractmethod
    async def save(self, config: AgentModelConfig) -> AgentModelConfig: ...

    @abstractmethod
    async def get_by_id(self, config_id: UUID) -> AgentModelConfig | None: ...

    @abstractmethod
    async def get_by_version(
        self, agent_id: UUID, version: str
    ) -> AgentModelConfig | None: ...

    @abstractmethod
    async def list_by_agent(
        self, agent_id: UUID
    ) -> list[AgentModelConfig]: ...

    @abstractmethod
    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentModelConfig]: ...


class AgentReleaseRepository(ABC):

    @abstractmethod
    async def save(self, release: AgentRelease) -> AgentRelease: ...

    @abstractmethod
    async def get_by_id(self, release_id: UUID) -> AgentRelease | None: ...

    @abstractmethod
    async def get_by_version(
        self, agent_id: UUID, version: str
    ) -> AgentRelease | None: ...

    @abstractmethod
    async def get_active_production(
        self, agent_id: UUID
    ) -> AgentRelease | None: ...

    @abstractmethod
    async def list_by_agent(
        self, agent_id: UUID
    ) -> list[AgentRelease]: ...

    @abstractmethod
    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentRelease]: ...

    @abstractmethod
    async def list_by_status(
        self, agent_id: UUID, status: ReleaseStatus
    ) -> list[AgentRelease]: ...

    @abstractmethod
    async def get_last_promoted(
        self, agent_id: UUID, *, exclude_id: UUID
    ) -> AgentRelease | None: ...

    @abstractmethod
    async def delete(self, release_id: UUID) -> None: ...


class AgentReleaseTestRepository(ABC):

    @abstractmethod
    async def save(self, test: AgentReleaseTest) -> AgentReleaseTest: ...

    @abstractmethod
    async def get_by_id(self, test_id: UUID) -> AgentReleaseTest | None: ...

    @abstractmethod
    async def list_by_release(
        self, release_id: UUID
    ) -> list[AgentReleaseTest]: ...

    @abstractmethod
    async def paginate_by_release(
        self, release_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentReleaseTest]: ...


class DocumentCollectionRepository(ABC):

    @abstractmethod
    async def create(self, collection: DocumentCollection) -> DocumentCollection: ...

    @abstractmethod
    async def get_by_id(self, collection_id: UUID) -> DocumentCollection: ...

    @abstractmethod
    async def list_by_project(
        self, project_id: UUID, status: str | None = None
    ) -> list[DocumentCollection]: ...

    @abstractmethod
    async def paginate_by_project(
        self, project_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[DocumentCollection]: ...

    @abstractmethod
    async def update(self, collection: DocumentCollection) -> DocumentCollection: ...

    @abstractmethod
    async def delete(self, collection_id: UUID) -> None: ...


class DocumentRepository(ABC):

    @abstractmethod
    async def create(self, document: Document) -> Document: ...

    @abstractmethod
    async def get_by_id(self, document_id: UUID) -> Document: ...

    @abstractmethod
    async def list_by_collection(
        self, collection_id: UUID, status: str | None = None
    ) -> list[Document]: ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[Document]: ...

    @abstractmethod
    async def paginate_by_collection(
        self, collection_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Document]: ...

    @abstractmethod
    async def update(self, document: Document) -> Document: ...

    @abstractmethod
    async def delete(self, document_id: UUID) -> None: ...


class AgentCollectionRepository(ABC):

    @abstractmethod
    async def list_by_agent(
        self, agent_id: UUID
    ) -> list[AgentCollection]: ...

    @abstractmethod
    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentCollection]: ...

    @abstractmethod
    async def get_by_agent_and_collection(
        self, agent_id: UUID, collection_id: UUID
    ) -> AgentCollection | None: ...

    @abstractmethod
    async def create(self, link: AgentCollection) -> AgentCollection: ...

    @abstractmethod
    async def delete(self, link_id: UUID) -> None: ...


class DocumentChunkRepository(ABC):

    @abstractmethod
    async def create_many(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]: ...

    @abstractmethod
    async def get_by_id(self, chunk_id: UUID) -> DocumentChunk: ...

    @abstractmethod
    async def list_by_document(
        self, document_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[DocumentChunk]: ...

    @abstractmethod
    async def paginate_by_document(
        self, document_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[DocumentChunk]: ...

    @abstractmethod
    async def delete_by_document(self, document_id: UUID) -> None: ...

    @abstractmethod
    async def search_similar(
        self,
        embedding: list[float],
        collection_id: UUID,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[tuple[DocumentChunk, float]]: ...


class KnowledgeVersionRepository(ABC):

    @abstractmethod
    async def save(self, version: KnowledgeVersion) -> KnowledgeVersion: ...

    @abstractmethod
    async def get_by_id(self, version_id: UUID) -> KnowledgeVersion | None: ...

    @abstractmethod
    async def get_by_version(self, agent_id: UUID, version: str) -> KnowledgeVersion | None: ...

    @abstractmethod
    async def list_by_agent(self, agent_id: UUID) -> list[KnowledgeVersion]: ...

    @abstractmethod
    async def paginate_by_agent(self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None) -> CursorPage[KnowledgeVersion]: ...


class SessionRepository(ABC):

    @abstractmethod
    async def create(self, session: Session) -> Session: ...

    @abstractmethod
    async def get_by_id(self, session_id: UUID) -> Session: ...

    async def get_by_id_for_update(self, session_id: UUID) -> Session:
        """Load a Session with write serialization when the adapter supports it."""
        return await self.get_by_id(session_id)

    @abstractmethod
    async def get_by_external_id(
        self, project_id: UUID, agent_id: UUID, external_session_id: str
    ) -> Session: ...

    @abstractmethod
    async def list_by_agent(
        self, project_id: UUID, agent_id: UUID, status: str | None = None
    ) -> list[Session]: ...

    @abstractmethod
    async def list_by_project(
        self, project_id: UUID, status: str | None = None
    ) -> list[Session]: ...

    @abstractmethod
    async def paginate_by_project(
        self, project_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Session]: ...

    @abstractmethod
    async def update(self, session: Session) -> Session: ...

    @abstractmethod
    async def delete(self, session_id: UUID) -> None: ...


class MessageRepository(ABC):

    @abstractmethod
    async def create(self, message: Message) -> Message: ...

    @abstractmethod
    async def get_by_id(self, message_id: UUID) -> Message: ...

    @abstractmethod
    async def list_by_session(
        self, session_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[Message]: ...

    @abstractmethod
    async def paginate_by_session(
        self, session_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Message]: ...

    @abstractmethod
    async def count_by_session(self, session_id: UUID) -> int: ...

    @abstractmethod
    async def delete_by_session(self, session_id: UUID) -> None: ...


class AskJobRepository(ABC):

    @abstractmethod
    async def create(self, job: AskJob) -> AskJob: ...

    @abstractmethod
    async def get_by_id(self, job_id: UUID) -> AskJob: ...

    @abstractmethod
    async def list_pending(self, limit: int = 5) -> list[AskJob]: ...

    @abstractmethod
    async def mark_started(self, job_id: UUID) -> None: ...

    @abstractmethod
    async def mark_waiting(
        self, job_id: UUID, result: dict, trace_id: UUID | None
    ) -> None: ...

    @abstractmethod
    async def mark_completed(
        self, job_id: UUID, result: dict, trace_id: UUID
    ) -> None: ...

    @abstractmethod
    async def mark_failed(self, job_id: UUID, error: str) -> None: ...


class ToolRepository(ABC):

    @abstractmethod
    async def create(self, tool: Tool) -> Tool: ...

    @abstractmethod
    async def get_by_id(self, tool_id: UUID) -> Tool: ...

    @abstractmethod
    async def list_by_project(
        self, project_id: UUID, status: str | None = None
    ) -> list[Tool]: ...

    @abstractmethod
    async def list_by_agent(
        self, agent_id: UUID, status: str | None = None
    ) -> list[Tool]: ...

    @abstractmethod
    async def paginate_by_project(
        self, project_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Tool]: ...

    @abstractmethod
    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Tool]: ...

    @abstractmethod
    async def update(self, tool: Tool) -> Tool: ...

    @abstractmethod
    async def delete(self, tool_id: UUID) -> None: ...


class SecretRepository(ABC):

    @abstractmethod
    async def create(self, secret: Secret) -> Secret: ...

    @abstractmethod
    async def get_by_id(self, secret_id: UUID) -> Secret: ...

    @abstractmethod
    async def get_by_name(self, project_id: UUID, name: str) -> Secret: ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[Secret]: ...

    @abstractmethod
    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Secret]: ...

    @abstractmethod
    async def update(self, secret: Secret) -> Secret: ...

    @abstractmethod
    async def delete(self, secret_id: UUID) -> None: ...


class AgentOutboxRepository(ABC):
    """Application-facing contract for outbox lifecycle transitions."""

    @abstractmethod
    async def mark_published(self, event_id: UUID) -> None: ...

    @abstractmethod
    async def mark_retryable(
        self, event_id: UUID, error: str, available_at: datetime
    ) -> None: ...

    @abstractmethod
    async def mark_dead(self, event_id: UUID, error: str) -> None: ...


class AgentInboxRepository(ABC):
    """Application-facing contract for inbox lifecycle transitions."""

    @abstractmethod
    async def mark_processing(self, event_id: UUID, locked_by: str) -> None: ...

    @abstractmethod
    async def mark_processed(self, event_id: UUID) -> None: ...

    @abstractmethod
    async def mark_retryable(
        self, event_id: UUID, error: str, available_at: datetime
    ) -> None: ...

    @abstractmethod
    async def mark_dead(self, event_id: UUID, error: str) -> None: ...

    @abstractmethod
    async def mark_ignored(self, event_id: UUID, reason: str) -> None: ...
