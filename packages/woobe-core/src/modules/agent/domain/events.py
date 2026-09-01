from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import uuid6


@dataclass(frozen=True)
class AgentDomainEvent:
    event_id: UUID = field(default_factory=uuid6.uuid7)
    event_type: str = ""
    event_version: int = 1
    producer_module: str = "agent"
    routing_key: str = ""
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
    correlation_id: UUID = field(default_factory=uuid6.uuid7)
    causation_id: UUID | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.event_type:
            raise ValueError("event_type is required")
        if not self.routing_key:
            raise ValueError("routing_key is required")
        if not self.idempotency_key:
            raise ValueError("idempotency_key is required")

    @staticmethod
    def compute_idempotency_key(
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        discriminator: str = "",
    ) -> str:
        raw = f"{aggregate_type}:{aggregate_id}:{event_type}:{discriminator}"
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class AgentExecutionRequestedV1(AgentDomainEvent):
    event_type: str = "agent.execution.requested.v1"
    event_version: int = 1
    routing_key: str = "agent.execution.requested.v1"

    @classmethod
    def create(
        cls,
        agent_id: UUID,
        session_id: UUID,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentExecutionRequestedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.requested.v1",
            discriminator=str(session_id),
        )
        return cls(
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentExecutionCompletedV1(AgentDomainEvent):
    event_type: str = "agent.execution.completed.v1"
    event_version: int = 1
    routing_key: str = "agent.execution.completed.v1"

    @classmethod
    def create(
        cls,
        agent_id: UUID,
        session_id: UUID,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentExecutionCompletedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.completed.v1",
            discriminator=str(session_id),
        )
        return cls(
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentExecutionFailedV1(AgentDomainEvent):
    event_type: str = "agent.execution.failed.v1"
    event_version: int = 1
    routing_key: str = "agent.execution.failed.v1"

    @classmethod
    def create(
        cls,
        agent_id: UUID,
        session_id: UUID,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentExecutionFailedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.failed.v1",
            discriminator=str(session_id),
        )
        return cls(
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentExecutionStartedV1(AgentDomainEvent):
    event_type: str = "agent.execution.started.v1"
    event_version: int = 1
    routing_key: str = "agent.execution.started.v1"

    @classmethod
    def create(
        cls,
        agent_id: UUID,
        session_id: UUID,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentExecutionStartedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.started.v1",
            discriminator=str(session_id),
        )
        return cls(
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentExecutionLLMCompletedV1(AgentDomainEvent):
    event_type: str = "agent.execution.llm_completed.v1"
    event_version: int = 1
    routing_key: str = "agent.execution.llm_completed.v1"

    @classmethod
    def create(
        cls,
        agent_id: UUID,
        session_id: UUID,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentExecutionLLMCompletedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.llm_completed.v1",
            discriminator=str(session_id),
        )
        return cls(
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentExecutionToolCompletedV1(AgentDomainEvent):
    event_type: str = "agent.execution.tool_completed.v1"
    event_version: int = 1
    routing_key: str = "agent.execution.tool_completed.v1"

    @classmethod
    def create(
        cls,
        agent_id: UUID,
        session_id: UUID,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentExecutionToolCompletedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.tool_completed.v1",
            discriminator=str(session_id),
        )
        return cls(
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentToolCreatedV1(AgentDomainEvent):
    event_type: str = "agent.tool.created.v1"
    event_version: int = 1
    routing_key: str = "agent.tool.created.v1"

    @classmethod
    def create(
        cls,
        tool_id: UUID,
        project_id: UUID,
        agent_id: UUID | None,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentToolCreatedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="tool",
            aggregate_id=tool_id,
            event_type="agent.tool.created.v1",
            discriminator=str(tool_id),
        )
        return cls(
            payload={
                "tool_id": str(tool_id),
                "project_id": str(project_id),
                "agent_id": str(agent_id) if agent_id else None,
                **payload,
            },
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentToolUpdatedV1(AgentDomainEvent):
    event_type: str = "agent.tool.updated.v1"
    event_version: int = 1
    routing_key: str = "agent.tool.updated.v1"

    @classmethod
    def create(
        cls,
        tool_id: UUID,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentToolUpdatedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="tool",
            aggregate_id=tool_id,
            event_type="agent.tool.updated.v1",
            discriminator=str(tool_id),
        )
        return cls(
            payload={"tool_id": str(tool_id), **payload},
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentToolStatusChangedV1(AgentDomainEvent):
    event_type: str = "agent.tool.status_changed.v1"
    event_version: int = 1
    routing_key: str = "agent.tool.status_changed.v1"

    @classmethod
    def create(
        cls,
        tool_id: UUID,
        status: str,
        payload: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentToolStatusChangedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="tool",
            aggregate_id=tool_id,
            event_type="agent.tool.status_changed.v1",
            discriminator=str(tool_id),
        )
        return cls(
            payload={"tool_id": str(tool_id), "status": status, **(payload or {})},
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentSecretCreatedV1(AgentDomainEvent):
    event_type: str = "agent.secret.created.v1"
    event_version: int = 1
    routing_key: str = "agent.secret.created.v1"

    @classmethod
    def create(
        cls,
        secret_id: UUID,
        project_id: UUID,
        name: str,
        secret_type: str,
        payload: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentSecretCreatedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="secret",
            aggregate_id=secret_id,
            event_type="agent.secret.created.v1",
            discriminator=str(secret_id),
        )
        return cls(
            payload={
                "secret_id": str(secret_id),
                "project_id": str(project_id),
                "name": name,
                "type": secret_type,
                **(payload or {}),
            },
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentKnowledgeDocumentIndexedV1(AgentDomainEvent):
    event_type: str = "agent.knowledge.document_indexed.v1"
    event_version: int = 1
    routing_key: str = "agent.knowledge.document_indexed.v1"

    @classmethod
    def create(
        cls,
        document_id: UUID,
        collection_id: UUID,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentKnowledgeDocumentIndexedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="document",
            aggregate_id=document_id,
            event_type="agent.knowledge.document_indexed.v1",
            discriminator=str(collection_id),
        )
        return cls(
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentFallbackTriggeredV1(AgentDomainEvent):
    event_type: str = "agent.execution.fallback_triggered.v1"
    event_version: int = 1
    routing_key: str = "agent.execution.fallback_triggered.v1"

    @classmethod
    def create(
        cls,
        agent_id: UUID,
        session_id: UUID,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentFallbackTriggeredV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.fallback_triggered.v1",
            discriminator=str(session_id),
        )
        return cls(
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentSessionCreatedV1(AgentDomainEvent):
    event_type: str = "agent.execution.session.created.v1"
    event_version: int = 1
    routing_key: str = "agent.execution.session.created.v1"

    @classmethod
    def create(
        cls,
        session_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        payload: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentSessionCreatedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="session",
            aggregate_id=session_id,
            event_type="agent.execution.session.created.v1",
            discriminator=str(session_id),
        )
        return cls(
            payload={
                "session_id": str(session_id),
                "project_id": str(project_id),
                "agent_id": str(agent_id),
                **(payload or {}),
            },
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentMessageCreatedV1(AgentDomainEvent):
    event_type: str = "agent.execution.message.created.v1"
    event_version: int = 1
    routing_key: str = "agent.execution.message.created.v1"

    @classmethod
    def create(
        cls,
        message_id: UUID,
        session_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        role: str,
        payload: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentMessageCreatedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="message",
            aggregate_id=message_id,
            event_type="agent.execution.message.created.v1",
            discriminator=str(message_id),
        )
        return cls(
            payload={
                "message_id": str(message_id),
                "session_id": str(session_id),
                "project_id": str(project_id),
                "agent_id": str(agent_id),
                "role": role,
                **(payload or {}),
            },
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentCreatedV1(AgentDomainEvent):
    event_type: str = "agent.agent.created.v1"
    event_version: int = 1
    routing_key: str = "agent.agent.created.v1"

    @classmethod
    def create(
        cls,
        agent_id: UUID,
        project_id: UUID,
        name: str,
        provider: str,
        model: str,
        payload: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentCreatedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.agent.created.v1",
            discriminator=str(agent_id),
        )
        return cls(
            payload={
                "agent_id": str(agent_id),
                "project_id": str(project_id),
                "name": name,
                "provider": provider,
                "model": model,
                **(payload or {}),
            },
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentUpdatedV1(AgentDomainEvent):
    event_type: str = "agent.agent.updated.v1"
    event_version: int = 1
    routing_key: str = "agent.agent.updated.v1"

    @classmethod
    def create(
        cls,
        agent_id: UUID,
        project_id: UUID,
        name: str,
        provider: str,
        model: str,
        payload: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentUpdatedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.agent.updated.v1",
            discriminator=str(agent_id),
        )
        return cls(
            payload={
                "agent_id": str(agent_id),
                "project_id": str(project_id),
                "name": name,
                "provider": provider,
                "model": model,
                **(payload or {}),
            },
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentProviderCredentialCreatedV1(AgentDomainEvent):
    event_type: str = "agent.credential.created.v1"
    event_version: int = 1
    routing_key: str = "agent.credential.created.v1"

    @classmethod
    def create(
        cls,
        credential_id: UUID,
        project_id: UUID,
        provider: str,
        name: str,
        payload: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentProviderCredentialCreatedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="credential",
            aggregate_id=credential_id,
            event_type="agent.credential.created.v1",
            discriminator=str(credential_id),
        )
        return cls(
            payload={
                "credential_id": str(credential_id),
                "project_id": str(project_id),
                "provider": provider,
                "name": name,
                **(payload or {}),
            },
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentProviderCredentialUpdatedV1(AgentDomainEvent):
    event_type: str = "agent.credential.updated.v1"
    event_version: int = 1
    routing_key: str = "agent.credential.updated.v1"

    @classmethod
    def create(
        cls,
        credential_id: UUID,
        project_id: UUID,
        provider: str,
        name: str,
        payload: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentProviderCredentialUpdatedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="credential",
            aggregate_id=credential_id,
            event_type="agent.credential.updated.v1",
            discriminator=str(credential_id),
        )
        return cls(
            payload={
                "credential_id": str(credential_id),
                "project_id": str(project_id),
                "provider": provider,
                "name": name,
                **(payload or {}),
            },
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentCollectionCreatedV1(AgentDomainEvent):
    event_type: str = "agent.knowledge.collection.created.v1"
    event_version: int = 1
    routing_key: str = "agent.knowledge.collection.created.v1"

    @classmethod
    def create(
        cls,
        collection_id: UUID,
        project_id: UUID,
        name: str,
        payload: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentCollectionCreatedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="collection",
            aggregate_id=collection_id,
            event_type="agent.knowledge.collection.created.v1",
            discriminator=str(collection_id),
        )
        return cls(
            payload={
                "collection_id": str(collection_id),
                "project_id": str(project_id),
                "name": name,
                **(payload or {}),
            },
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


@dataclass(frozen=True)
class AgentDocumentUploadedV1(AgentDomainEvent):
    event_type: str = "agent.knowledge.document.uploaded.v1"
    event_version: int = 1
    routing_key: str = "agent.knowledge.document.uploaded.v1"

    @classmethod
    def create(
        cls,
        document_id: UUID,
        collection_id: UUID,
        project_id: UUID,
        file_name: str,
        storage_key: str,
        parser: str,
        payload: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentDocumentUploadedV1:
        idempotency_key = cls.compute_idempotency_key(
            aggregate_type="document",
            aggregate_id=document_id,
            event_type="agent.knowledge.document.uploaded.v1",
            discriminator=str(document_id),
        )
        return cls(
            payload={
                "document_id": str(document_id),
                "collection_id": str(collection_id),
                "project_id": str(project_id),
                "file_name": file_name,
                "storage_key": storage_key,
                "parser": parser,
                **(payload or {}),
            },
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )


# --- Event catalog ---

EVENT_CATALOG: dict[str, str] = {
    "agent.execution.requested.v1": "execution",
    "agent.execution.completed.v1": "execution",
    "agent.execution.failed.v1": "execution",
    "agent.execution.fallback_triggered.v1": "execution",
    "agent.execution.session.created.v1": "execution",
    "agent.execution.message.created.v1": "execution",
    "agent.tool.created.v1": "tool",
    "agent.tool.updated.v1": "tool",
    "agent.tool.status_changed.v1": "tool",
    "agent.secret.created.v1": "secret",
    "agent.credential.created.v1": "credential",
    "agent.credential.updated.v1": "credential",
    "agent.agent.created.v1": "agent",
    "agent.agent.updated.v1": "agent",
    "agent.knowledge.collection.created.v1": "knowledge",
    "agent.knowledge.document.uploaded.v1": "knowledge",
    "agent.knowledge.document_indexed.v1": "knowledge",
}

# --- Legacy event type compatibility mapping ---
# Maps deprecated event types to their canonical replacements.
LEGACY_EVENT_MAP: dict[str, str] = {
    "runtime.session.created": "agent.execution.session.created.v1",
    "runtime.ask.completed": "agent.execution.message.created.v1",
    "agent.created": "agent.agent.created.v1",
    "agent.updated": "agent.agent.updated.v1",
    "knowledge.collection.created": "agent.knowledge.collection.created.v1",
    "knowledge.document.uploaded": "agent.knowledge.document.uploaded.v1",
    "provider_credential.created": "agent.credential.created.v1",
    "provider_credential.updated": "agent.credential.updated.v1",
}


def resolve_event_type(event_type: str) -> str:
    """Resolve deprecated event types to canonical form, with deprecation warning."""
    canonical = LEGACY_EVENT_MAP.get(event_type)
    if canonical:
        warnings.warn(
            f"Event type '{event_type}' is deprecated, use '{canonical}' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return canonical
    return event_type
