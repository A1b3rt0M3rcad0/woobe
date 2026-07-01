from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from shared.domain.pagination import CursorPage

from modules.agent.domain.entities import (
    Agent,
    AgentCollection,
    AgentContract,
    AgentPrompt,
    AgentRelease,
    AgentReleaseTest,
    AgentTool,
    AgentToolSecret,
    AskJob,
    Document,
    DocumentChunk,
    DocumentCollection,
    KnowledgeVersion,
    Message,
    ModelConfig,
    ProviderCredential,
    ProviderModel,
    Session,
)
from modules.agent.domain.enums import Provider, ProviderCredentialStatus, ReleaseStatus


class ProviderCredentialRepository(ABC):
    @abstractmethod
    async def create(self, credential: ProviderCredential) -> ProviderCredential: ...

    @abstractmethod
    async def get_by_id(self, credential_id: UUID) -> ProviderCredential: ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID, provider: Provider | None = None, status: ProviderCredentialStatus | None = None) -> list[ProviderCredential]: ...

    @abstractmethod
    async def update(self, credential: ProviderCredential) -> ProviderCredential: ...

    @abstractmethod
    async def delete(self, credential_id: UUID) -> None: ...


class ProviderModelRepository(ABC):
    @abstractmethod
    async def save(self, model: ProviderModel) -> ProviderModel: ...

    @abstractmethod
    async def get_by_id(self, model_id: UUID) -> ProviderModel | None: ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID, *, provider: Provider | None = None, status: str | None = None) -> list[ProviderModel]: ...

    @abstractmethod
    async def update(self, model: ProviderModel) -> ProviderModel: ...


class AgentRepository(ABC):
    @abstractmethod
    async def create(self, agent: Agent) -> Agent: ...

    @abstractmethod
    async def get_by_id(self, agent_id: UUID) -> Agent: ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[Agent]: ...

    @abstractmethod
    async def update(self, agent: Agent) -> Agent: ...

    @abstractmethod
    async def delete(self, agent_id: UUID) -> None: ...


class AgentPromptRepository(ABC):
    @abstractmethod
    async def create(self, prompt: AgentPrompt) -> AgentPrompt: ...

    @abstractmethod
    async def get_by_id(self, prompt_id: UUID) -> AgentPrompt: ...

    @abstractmethod
    async def get_by_agent_version(self, agent_id: UUID, version: str) -> AgentPrompt | None: ...

    @abstractmethod
    async def list_by_agent(self, agent_id: UUID) -> list[AgentPrompt]: ...

    @abstractmethod
    async def update(self, prompt: AgentPrompt) -> AgentPrompt: ...


class AgentContractRepository(ABC):
    @abstractmethod
    async def create(self, contract: AgentContract) -> AgentContract: ...

    @abstractmethod
    async def get_by_id(self, contract_id: UUID) -> AgentContract: ...

    @abstractmethod
    async def get_by_agent_version(self, agent_id: UUID, version: str) -> AgentContract | None: ...

    @abstractmethod
    async def list_by_agent(self, agent_id: UUID) -> list[AgentContract]: ...

    @abstractmethod
    async def update(self, contract: AgentContract) -> AgentContract: ...


class ModelConfigRepository(ABC):
    @abstractmethod
    async def create(self, config: ModelConfig) -> ModelConfig: ...

    @abstractmethod
    async def get_by_id(self, config_id: UUID) -> ModelConfig: ...

    @abstractmethod
    async def get_by_agent_version(self, agent_id: UUID, version: str) -> ModelConfig | None: ...

    @abstractmethod
    async def list_by_agent(self, agent_id: UUID) -> list[ModelConfig]: ...

    @abstractmethod
    async def update(self, config: ModelConfig) -> ModelConfig: ...


class AgentReleaseRepository(ABC):
    @abstractmethod
    async def create(self, release: AgentRelease) -> AgentRelease: ...

    @abstractmethod
    async def get_by_id(self, release_id: UUID) -> AgentRelease | None: ...

    @abstractmethod
    async def get_active_production(self, agent_id: UUID) -> AgentRelease | None: ...

    @abstractmethod
    async def list_by_agent(self, agent_id: UUID) -> list[AgentRelease]: ...

    @abstractmethod
    async def list_by_status(self, agent_id: UUID, status: ReleaseStatus) -> list[AgentRelease]: ...

    @abstractmethod
    async def get_last_promoted(self, agent_id: UUID, *, exclude_id: UUID) -> AgentRelease | None: ...

    @abstractmethod
    async def update(self, release: AgentRelease) -> AgentRelease: ...

    @abstractmethod
    async def delete(self, release_id: UUID) -> None: ...


class AgentReleaseTestRepository(ABC):
    @abstractmethod
    async def save(self, test: AgentReleaseTest) -> AgentReleaseTest: ...

    @abstractmethod
    async def get_by_id(self, test_id: UUID) -> AgentReleaseTest | None: ...

    @abstractmethod
    async def list_by_release(self, release_id: UUID) -> list[AgentReleaseTest]: ...


class DocumentCollectionRepository(ABC):
    @abstractmethod
    async def create(self, collection: DocumentCollection) -> DocumentCollection: ...

    @abstractmethod
    async def get_by_id(self, collection_id: UUID) -> DocumentCollection: ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID, status: str | None = None) -> list[DocumentCollection]: ...

    @abstractmethod
    async def paginate_by_project(self, project_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None) -> CursorPage[DocumentCollection]: ...

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
    async def get_active_by_project_and_sha256(self, project_id: UUID, sha256: str) -> Document | None: ...

    @abstractmethod
    async def list_by_collection(self, collection_id: UUID, status: str | None = None) -> list[Document]: ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[Document]: ...

    @abstractmethod
    async def paginate_by_collection(self, collection_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None) -> CursorPage[Document]: ...

    @abstractmethod
    async def update(self, document: Document) -> Document: ...

    @abstractmethod
    async def delete(self, document_id: UUID) -> None: ...


class AgentCollectionRepository(ABC):
    @abstractmethod
    async def list_by_agent(self, agent_id: UUID) -> list[AgentCollection]: ...

    @abstractmethod
    async def get_by_agent_and_collection(self, agent_id: UUID, collection_id: UUID) -> AgentCollection | None: ...

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
    async def list_by_document(self, document_id: UUID, offset: int = 0, limit: int = 100) -> list[DocumentChunk]: ...

    @abstractmethod
    async def delete_by_document(self, document_id: UUID) -> None: ...

    @abstractmethod
    async def search_similar(self, embedding: list[float], collection_id: UUID, limit: int = 10, threshold: float = 0.7) -> list[tuple[DocumentChunk, float]]: ...


class KnowledgeVersionRepository(ABC):
    @abstractmethod
    async def save(self, version: KnowledgeVersion) -> KnowledgeVersion: ...

    @abstractmethod
    async def get_by_id(self, version_id: UUID) -> KnowledgeVersion | None: ...

    @abstractmethod
    async def list_by_agent(self, agent_id: UUID) -> list[KnowledgeVersion]: ...


class SessionRepository(ABC):
    @abstractmethod
    async def create(self, session: Session) -> Session: ...

    @abstractmethod
    async def get_by_id(self, session_id: UUID) -> Session: ...

    @abstractmethod
    async def list_by_agent(self, agent_id: UUID, limit: int = 50) -> list[Session]: ...


class MessageRepository(ABC):
    @abstractmethod
    async def create(self, message: Message) -> Message: ...

    @abstractmethod
    async def get_by_id(self, message_id: UUID) -> Message: ...

    @abstractmethod
    async def list_by_session(self, session_id: UUID, limit: int = 50) -> list[Message]: ...


class AskJobRepository(ABC):
    @abstractmethod
    async def create(self, job: AskJob) -> AskJob: ...

    @abstractmethod
    async def get_by_id(self, job_id: UUID) -> AskJob: ...

    @abstractmethod
    async def list_pending(self, limit: int = 10) -> list[AskJob]: ...

    @abstractmethod
    async def update(self, job: AskJob) -> AskJob: ...


class AgentToolRepository(ABC):
    @abstractmethod
    async def save(self, tool: AgentTool) -> AgentTool: ...


class AgentToolSecretRepository(ABC):
    @abstractmethod
    async def save(self, secret: AgentToolSecret) -> AgentToolSecret: ...
