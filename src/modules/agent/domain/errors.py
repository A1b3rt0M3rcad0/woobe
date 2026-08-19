from __future__ import annotations

from typing import Any
from uuid import UUID

from shared.contracts.errors import ConflictError, NotFoundError


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


class RuntimeEnvironmentNotReadyError(ConflictError):
    def __init__(self, environment: str, agent_id: UUID) -> None:
        self.environment = environment
        self.agent_id = agent_id
        super().__init__(
            f"No {environment} release is deployed for agent {agent_id}."
        )


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


class SessionNotFoundError(NotFoundError):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")


class MessageNotFoundError(NotFoundError):
    def __init__(self, message_id: UUID) -> None:
        self.message_id = message_id
        super().__init__(f"Message not found: {message_id}")


class AskJobNotFoundError(NotFoundError):
    def __init__(self, job_id: UUID) -> None:
        self.job_id = job_id
        super().__init__(f"Ask job not found: {job_id}")


class ToolNotFoundError(NotFoundError):
    def __init__(self, tool_id: UUID) -> None:
        self.tool_id = tool_id
        super().__init__(f"Tool not found: {tool_id}")


class ToolInUseError(ConflictError):
    def __init__(self, tool_id: UUID, impact: Any) -> None:
        self.tool_id = tool_id
        self.impact = impact
        super().__init__(
            "Tool cannot be permanently deleted because it is referenced by "
            "Agent versions. Retire the Tool instead."
        )


class SecretNotFoundError(NotFoundError):
    def __init__(self, secret_id: UUID) -> None:
        self.secret_id = secret_id
        super().__init__(f"Secret not found: {secret_id}")


class DuplicateSecretError(ConflictError):
    def __init__(self, name: str, project_id: UUID) -> None:
        self.name = name
        self.project_id = project_id
        super().__init__(f"Secret '{name}' already exists in project {project_id}")
