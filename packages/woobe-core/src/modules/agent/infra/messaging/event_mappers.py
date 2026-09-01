from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

import uuid6

from modules.agent.domain.events import AgentDomainEvent
from modules.agent.infra.database.models import (
    AgentInboxEventModel,
    AgentOutboxEventModel,
)


@dataclass(frozen=True)
class RabbitMQMessageEnvelope:
    routing_key: str
    body: str
    correlation_id: str
    headers: dict[str, Any] = field(default_factory=dict)
    message_id: str = ""


class IncomingMessage(Protocol):
    @property
    def body(self) -> bytes: ...

    @property
    def routing_key(self) -> str | None: ...

    @property
    def correlation_id(self) -> str | None: ...

    @property
    def headers(self) -> dict[str, Any] | None: ...

    @property
    def message_id(self) -> str | None: ...


_REPEATABLE_MUTATION_EVENT_TYPES = frozenset(
    {
        "agent.agent.updated.v1",
        "agent.tool.updated.v1",
        "agent.tool.status_changed.v1",
        "agent.credential.updated.v1",
    }
)

_NETWORK_CONTEXT_FIELDS = (
    "network_id",
    "network_version_id",
    "network_session_id",
    "network_execution_id",
    "network_invocation_id",
    "parent_invocation_id",
    "network_node_id",
    "depth",
)


def _active_network_context_payload() -> dict[str, Any]:
    """Return Network runtime identity without coupling event callers to Network."""
    from modules.agent.application.interfaces.execution_context import current_execution

    context = current_execution.get()
    if context is None or context.network_id is None:
        return {}
    payload: dict[str, Any] = {}
    for field_name in _NETWORK_CONTEXT_FIELDS:
        value = getattr(context, field_name, None)
        if value is not None:
            payload[field_name] = str(value) if isinstance(value, UUID) else value
    return payload


def _validate_event_fields(
    event_version: int,
    routing_key: str,
    idempotency_key: str,
    correlation_id: UUID | None,
) -> None:
    if event_version < 1:
        raise ValueError(f"Invalid event_version: {event_version}")
    if not routing_key:
        raise ValueError("routing_key is required")
    if not idempotency_key:
        raise ValueError("idempotency_key is required")
    if correlation_id is None:
        raise ValueError("correlation_id is required")


def _execution_occurrence(event: AgentDomainEvent) -> str:
    trace_id = event.payload.get("trace_id") or event.payload.get("execution_id")
    trace_occurrence = str(trace_id or event.event_id)

    if event.event_type == "agent.execution.llm_completed.v1":
        call_occurrence = (
            event.payload.get("call_id")
            or event.payload.get("call_index")
            or event.event_id
        )
        return f"{trace_occurrence}:{call_occurrence}"

    if event.event_type == "agent.execution.tool_completed.v1":
        tool_occurrence = (
            event.payload.get("tool_call_id")
            or event.payload.get("tool_id")
            or event.event_id
        )
        return f"{trace_occurrence}:{tool_occurrence}"

    return trace_occurrence


def _mutation_occurrence(event: AgentDomainEvent) -> str:
    """Return the identifier for one concrete mutation occurrence.

    Update-style events are repeatable for the same aggregate. Their domain-level
    idempotency key is intentionally stable, but the outbox unique constraint
    must distinguish separate successful mutations. A caller-provided operation
    or request identifier takes precedence; otherwise the immutable event id is
    used. Mapping the same event object twice still produces the same key.
    """
    metadata = event.metadata or {}
    occurrence = (
        event.payload.get("operation_id")
        or event.payload.get("request_id")
        or metadata.get("operation_id")
        or metadata.get("request_id")
        or event.event_id
    )
    return str(occurrence)


def _effective_idempotency_key(event: AgentDomainEvent) -> str:
    """Build an idempotency key for one concrete event occurrence.

    Execution events are scoped by trace. Event types that can occur more than
    once in the same trace also include their call identifier. Repeatable
    mutation events are scoped by operation occurrence so distinct updates of
    the same aggregate do not collide with the outbox unique constraint.
    """
    if event.event_type.startswith("agent.execution."):
        occurrence = _execution_occurrence(event)
        raw = f"agent:{event.event_type}:{occurrence}"
        return hashlib.sha256(raw.encode()).hexdigest()

    if event.event_type in _REPEATABLE_MUTATION_EVENT_TYPES:
        occurrence = _mutation_occurrence(event)
        raw = f"agent:{event.event_type}:{event.idempotency_key}:{occurrence}"
        return hashlib.sha256(raw.encode()).hexdigest()

    return event.idempotency_key


def domain_event_to_outbox(event: AgentDomainEvent) -> AgentOutboxEventModel:
    idempotency_key = _effective_idempotency_key(event)
    _validate_event_fields(
        event_version=event.event_version,
        routing_key=event.routing_key,
        idempotency_key=idempotency_key,
        correlation_id=event.correlation_id,
    )
    payload = dict(event.payload)
    if event.event_type.startswith("agent.execution."):
        payload = {**_active_network_context_payload(), **payload}
    aggregate_type = payload.get("aggregate_type", "")
    aggregate_id = payload.get("aggregate_id")
    if not aggregate_type:
        aggregate_type = "agent"
    if aggregate_id is None:
        aggregate_id = event.event_id
    else:
        aggregate_id = UUID(aggregate_id) if isinstance(aggregate_id, str) else aggregate_id
    model = AgentOutboxEventModel()
    model.id = event.event_id
    model.aggregate_type = aggregate_type
    model.aggregate_id = aggregate_id
    model.event_type = event.event_type
    model.event_version = event.event_version
    model.routing_key = event.routing_key
    model.payload = payload
    model.metadata_ = event.metadata
    model.idempotency_key = idempotency_key
    model.correlation_id = event.correlation_id
    model.causation_id = event.causation_id
    model.status = "pending"
    model.attempts = 0
    model.available_at = datetime.now(timezone.utc)
    model.created_at = datetime.now(timezone.utc)
    model.updated_at = datetime.now(timezone.utc)
    return model


def outbox_to_rabbit_message(event: AgentOutboxEventModel) -> RabbitMQMessageEnvelope:
    _validate_event_fields(
        event_version=event.event_version,
        routing_key=event.routing_key,
        idempotency_key=event.idempotency_key,
        correlation_id=event.correlation_id,
    )
    body_dict = {
        "event_id": str(event.id),
        "event_type": event.event_type,
        "event_version": event.event_version,
        "producer_module": "agent",
        "routing_key": event.routing_key,
        "occurred_at": event.created_at.isoformat() if event.created_at else None,
        "payload": event.payload,
        "idempotency_key": event.idempotency_key,
        "correlation_id": str(event.correlation_id),
        "causation_id": str(event.causation_id) if event.causation_id else None,
        "metadata": event.metadata_,
    }
    headers = {
        "x-event-type": event.event_type,
        "x-event-version": str(event.event_version),
        "x-producer-module": "agent",
        "x-idempotency-key": event.idempotency_key,
    }
    return RabbitMQMessageEnvelope(
        routing_key=event.routing_key,
        body=json.dumps(body_dict, default=str),
        correlation_id=str(event.correlation_id),
        headers=headers,
        message_id=str(event.id),
    )


def rabbit_message_to_inbox(message: IncomingMessage) -> AgentInboxEventModel:
    body = json.loads(message.body.decode())
    event_type = body.get("event_type", "")
    event_version = body.get("event_version", 1)
    routing_key = body.get("routing_key", message.routing_key or "")
    idempotency_key = body.get("idempotency_key", "")
    correlation_id_str = body.get("correlation_id")
    correlation_id = UUID(correlation_id_str) if correlation_id_str else uuid6.uuid7()

    _validate_event_fields(
        event_version=event_version,
        routing_key=routing_key,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )

    causation_id_str = body.get("causation_id")
    causation_id = UUID(causation_id_str) if causation_id_str else None
    message_id = message.message_id or str(uuid6.uuid7())
    producer_module = body.get("producer_module", "unknown")

    model = AgentInboxEventModel()
    model.id = uuid6.uuid7()
    model.message_id = message_id
    model.producer_module = producer_module
    model.consumer_module = "agent"
    model.event_type = event_type
    model.event_version = event_version
    model.routing_key = routing_key
    model.payload = body.get("payload", {})
    model.headers = dict(message.headers) if message.headers else None
    model.idempotency_key = idempotency_key
    model.correlation_id = correlation_id
    model.causation_id = causation_id
    model.status = "received"
    model.attempts = 0
    model.available_at = datetime.now(timezone.utc)
    model.created_at = datetime.now(timezone.utc)
    model.updated_at = datetime.now(timezone.utc)
    return model
