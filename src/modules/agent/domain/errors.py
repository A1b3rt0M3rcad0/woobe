from __future__ import annotations

from uuid import UUID

from shared.domain.errors import ConflictError, NotFoundError


class CredentialNotFoundError(NotFoundError):
    pass


class AgentNotFoundError(NotFoundError):
    pass


class PromptNotFoundError(NotFoundError):
    pass


class ContractNotFoundError(NotFoundError):
    pass


class ModelConfigNotFoundError(NotFoundError):
    pass


class ReleaseNotFoundError(NotFoundError):
    pass


class ReleaseTestNotFoundError(NotFoundError):
    pass


class CollectionNotFoundError(NotFoundError):
    def __init__(self, collection_id: UUID) -> None:
        self.collection_id = collection_id
        super().__init__(f"Document collection not found: {collection_id}")


class DocumentNotFoundError(NotFoundError):
    def __init__(self, document_id: UUID) -> None:
        self.document_id = document_id
        super().__init__(f"Document not found: {document_id}")


class ChunkNotFoundError(NotFoundError):
    def __init__(self, chunk_id: UUID) -> None:
        self.chunk_id = chunk_id
        super().__init__(f"Document chunk not found: {chunk_id}")


class DuplicateCollectionError(ConflictError):
    def __init__(self, name: str, project_id: UUID) -> None:
        self.name = name
        self.project_id = project_id
        super().__init__(f"Collection '{name}' already exists in project {project_id}")


class KnowledgeVersionNotFoundError(NotFoundError):
    def __init__(self, version_id: UUID) -> None:
        self.version_id = version_id
        super().__init__(f"Knowledge version not found: {version_id}")
