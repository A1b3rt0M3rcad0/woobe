"""Standardized event envelope for inter-module messaging.

All events published via Outbox and consumed via Inbox must conform to this envelope:
1. event_type and routing_key follow '<producer_module>.<domain_event>.v<version>'.
2. payload must not contain ORM objects or full serialized entities without contract.
3. Every field marked as required must be present and non-empty.
4. event_version must be a positive integer matching the version suffix in event_type.

This module provides:
- EventEnvelope: the wire-format dataclass.
- IntegrationEvent: the domain-level event class with validation and serialization.
- EventSerializer/EventDeserializer: serialize and deserialize to/from dict/JSON.
- EventEnvelopeValidationError: raised when envelope validation fails.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar
from uuid import UUID

import uuid6


EVENT_TYPE_PATTERN: re.Pattern[str] = re.compile(
    r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,}\.v\d+$"
)

ROUTING_KEY_PATTERN: re.Pattern[str] = re.compile(
    r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){2,}$"
)

REQUIRED_ENVELOPE_FIELDS: frozenset[str] = frozenset(
    [
        "event_id",
        "event_type",
        "event_version",
        "producer_module",
        "routing_key",
        "occurred_at",
        "payload",
        "idempotency_key",
        "correlation_id",
    ]
)

OPTIONAL_ENVELOPE_FIELDS: frozenset[str] = frozenset(
    [
        "causation_id",
        "metadata",
        "aggregate_type",
        "aggregate_id",
    ]
)


@dataclass(frozen=True)
class EventEnvelope:
    event_id: UUID
    event_type: str
    event_version: int
    producer_module: str
    routing_key: str
    occurred_at: datetime
    payload: dict[str, Any]
    idempotency_key: str
    correlation_id: UUID
    causation_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    aggregate_type: str | None = None
    aggregate_id: UUID | None = None


@dataclass(frozen=True)
class IntegrationEvent:
    """Canonical domain-level integration event.

    All cross-module state changes must use this class as the standard envelope.
    The event_id is used as message_id for deduplication.
    """

    event_id: UUID = field(default_factory=uuid6.uuid7)
    event_type: str = ""
    event_version: int = 1
    producer_module: str = ""
    routing_key: str = ""
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
    correlation_id: UUID = field(default_factory=uuid6.uuid7)
    causation_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    aggregate_type: str | None = None
    aggregate_id: UUID | None = None

    _MESSAGE_ID_FIELD: ClassVar[str] = "event_id"

    def __post_init__(self) -> None:
        if not self.event_type:
            raise ValueError("event_type is required")
        if not self.producer_module:
            raise ValueError("producer_module is required")
        if not self.routing_key:
            raise ValueError("routing_key is required")
        if not self.idempotency_key:
            raise ValueError("idempotency_key is required")

    @property
    def message_id(self) -> str:
        return str(self.event_id)

    @staticmethod
    def compute_idempotency_key(
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        discriminator: str = "",
    ) -> str:
        raw = f"{aggregate_type}:{aggregate_id}:{event_type}:{discriminator}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_envelope(self) -> EventEnvelope:
        return EventEnvelope(
            event_id=self.event_id,
            event_type=self.event_type,
            event_version=self.event_version,
            producer_module=self.producer_module,
            routing_key=self.routing_key,
            occurred_at=self.occurred_at,
            payload=self.payload,
            idempotency_key=self.idempotency_key,
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            metadata=self.metadata,
            aggregate_type=self.aggregate_type,
            aggregate_id=self.aggregate_id,
        )

    @classmethod
    def from_envelope(cls, envelope: EventEnvelope) -> IntegrationEvent:
        return cls(
            event_id=envelope.event_id,
            event_type=envelope.event_type,
            event_version=envelope.event_version,
            producer_module=envelope.producer_module,
            routing_key=envelope.routing_key,
            occurred_at=envelope.occurred_at,
            payload=envelope.payload,
            idempotency_key=envelope.idempotency_key,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            metadata=envelope.metadata,
            aggregate_type=envelope.aggregate_type,
            aggregate_id=envelope.aggregate_id,
        )


class EventEnvelopeValidationError(ValueError):
    pass


def validate_event_envelope(envelope: dict[str, Any]) -> None:
    missing = REQUIRED_ENVELOPE_FIELDS - set(envelope.keys())
    if missing:
        raise EventEnvelopeValidationError(
            f"Missing required envelope fields: {sorted(missing)}"
        )

    event_type = envelope.get("event_type", "")
    if not event_type or not isinstance(event_type, str):
        raise EventEnvelopeValidationError("event_type must be a non-empty string")
    if not EVENT_TYPE_PATTERN.match(event_type):
        raise EventEnvelopeValidationError(
            f"event_type must match '<module>.<event>.v<N>' pattern, "
            f"got: '{event_type}'"
        )

    event_version = envelope.get("event_version")
    if not isinstance(event_version, int) or event_version < 1:
        raise EventEnvelopeValidationError(
            f"event_version must be a positive integer, got: {event_version}"
        )

    version_suffix = f".v{event_version}"
    if not event_type.endswith(version_suffix):
        raise EventEnvelopeValidationError(
            f"event_type version suffix must match event_version: "
            f"expected ending '.v{event_version}', got: '{event_type}'"
        )

    routing_key = envelope.get("routing_key", "")
    if not routing_key or not isinstance(routing_key, str):
        raise EventEnvelopeValidationError("routing_key must be a non-empty string")
    if not ROUTING_KEY_PATTERN.match(routing_key):
        raise EventEnvelopeValidationError(
            f"routing_key must match '<module>.<entity>.<action>[.vN]' pattern, "
            f"got: '{routing_key}'"
        )

    producer_module = envelope.get("producer_module", "")
    if not producer_module or not isinstance(producer_module, str):
        raise EventEnvelopeValidationError(
            "producer_module must be a non-empty string"
        )
    if not event_type.startswith(f"{producer_module}."):
        raise EventEnvelopeValidationError(
            f"event_type must start with producer_module prefix: "
            f"expected '{producer_module}.', got: '{event_type}'"
        )

    idempotency_key = envelope.get("idempotency_key", "")
    if not idempotency_key or not isinstance(idempotency_key, str):
        raise EventEnvelopeValidationError(
            "idempotency_key must be a non-empty string"
        )

    correlation_id = envelope.get("correlation_id")
    if not correlation_id:
        raise EventEnvelopeValidationError(
            "correlation_id is required and must be non-empty"
        )

    occurred_at = envelope.get("occurred_at")
    if not occurred_at:
        raise EventEnvelopeValidationError(
            "occurred_at is required and must be non-empty"
        )

    event_id = envelope.get("event_id")
    if not event_id:
        raise EventEnvelopeValidationError(
            "event_id is required and must be non-empty"
        )

    payload = envelope.get("payload")
    if payload is not None and not isinstance(payload, dict):
        raise EventEnvelopeValidationError(
            "payload must be a dict or null"
        )


class EventSerializer:
    """Serialize IntegrationEvent to dict or JSON string."""

    @staticmethod
    def to_dict(event: IntegrationEvent) -> dict[str, Any]:
        return {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "event_version": event.event_version,
            "producer_module": event.producer_module,
            "routing_key": event.routing_key,
            "occurred_at": event.occurred_at.isoformat(),
            "payload": event.payload,
            "idempotency_key": event.idempotency_key,
            "correlation_id": str(event.correlation_id),
            "causation_id": str(event.causation_id) if event.causation_id else None,
            "metadata": event.metadata,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": str(event.aggregate_id) if event.aggregate_id else None,
        }

    @staticmethod
    def to_json(event: IntegrationEvent) -> str:
        return json.dumps(EventSerializer.to_dict(event), default=str)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> IntegrationEvent:
        occurred_str = data.get("occurred_at")
        occurred_at: datetime
        if isinstance(occurred_str, str):
            occurred_at = datetime.fromisoformat(occurred_str)
        else:
            occurred_at = datetime.now(timezone.utc)

        causation_id_raw = data.get("causation_id")
        causation_id: UUID | None = (
            UUID(causation_id_raw) if causation_id_raw else None
        )

        aggregate_id_raw = data.get("aggregate_id")
        aggregate_id: UUID | None = (
            UUID(aggregate_id_raw) if aggregate_id_raw else None
        )

        event_id_raw = data.get("event_id")
        event_id = UUID(event_id_raw) if event_id_raw else uuid6.uuid7()

        correlation_id_raw = data.get("correlation_id")
        correlation_id = (
            UUID(correlation_id_raw) if correlation_id_raw else uuid6.uuid7()
        )

        return IntegrationEvent(
            event_id=event_id,
            event_type=data.get("event_type", ""),
            event_version=data.get("event_version", 1),
            producer_module=data.get("producer_module", ""),
            routing_key=data.get("routing_key", ""),
            occurred_at=occurred_at,
            payload=data.get("payload", {}),
            idempotency_key=data.get("idempotency_key", ""),
            correlation_id=correlation_id,
            causation_id=causation_id,
            metadata=data.get("metadata", {}),
            aggregate_type=data.get("aggregate_type"),
            aggregate_id=aggregate_id,
        )

    @staticmethod
    def from_json(raw: str) -> IntegrationEvent:
        return EventSerializer.from_dict(json.loads(raw))

    @staticmethod
    def validate_dict(data: dict[str, Any]) -> None:
        validate_event_envelope(data)
