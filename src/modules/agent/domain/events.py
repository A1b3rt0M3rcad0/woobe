from __future__ import annotations

import hashlib
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
