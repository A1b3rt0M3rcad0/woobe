from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from modules.knowledge.domain.entities import (
    AgentCollection,
    Document,
    DocumentChunk,
    DocumentCollection,
    KnowledgeVersion,
)
from shared.domain.objects import CursorPage


class DocumentCollectionRepository(ABC):

    @abstractmethod
    async def create(self, collection: DocumentCollection) -> DocumentCollection: ...

    @abstractmethod
    async def get_by_id(self, collection_id: UUID) -> DocumentCollection: ...

    @abstractmethod
    async def list_by_project(
        self, project_id: UUID, status: str | None = None
    ) -> list[DocumentCollection]: ...  # TODO: Remove after pagination migration

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
    ) -> list[Document]: ...  # TODO: Remove after pagination migration

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
    ) -> list[AgentCollection]: ...  # TODO: Remove after pagination migration

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
    ) -> list[DocumentChunk]: ...  # TODO: Remove after pagination migration

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

