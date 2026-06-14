"""Standardized event envelope for inter-module messaging.

All events published via Outbox and consumed via Inbox must conform to this envelope:
1. event_type and routing_key follow '<producer_module>.<domain_event>.v<version>'.
2. payload must not contain ORM objects or full serialized entities without contract.
3. Every field marked as required must be present and non-empty.
4. event_version must be a positive integer matching the version suffix in event_type.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


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
