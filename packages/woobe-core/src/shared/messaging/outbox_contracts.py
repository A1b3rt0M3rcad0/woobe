"""Standardized module outbox pattern contracts.

Every module that publishes events must conform to this contract:
1. Each module owns its Outbox table in its own schema/namespace.
2. The publisher does not know consumers.
3. Event type and routing key must be versioned (e.g. "module.entity.action.v1").
4. The Outbox status may only be marked `published` after broker publisher confirm.
5. The published envelope must contain all REQUIRED_ENVELOPE_FIELDS.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import UUID


REQUIRED_ENVELOPE_FIELDS: frozenset[str] = frozenset(
    [
        "event_id",
        "event_type",
        "event_version",
        "occurred_at",
        "producer_module",
        "routing_key",
        "payload",
        "idempotency_key",
        "correlation_id",
    ]
)

OPTIONAL_ENVELOPE_FIELDS: frozenset[str] = frozenset(
    [
        "aggregate_type",
        "aggregate_id",
        "causation_id",
        "metadata",
    ]
)

ROUTING_KEY_MIN_SEGMENTS: int = 3


@runtime_checkable
class OutboxEventProtocol(Protocol):
    @property
    def event_type(self) -> str: ...

    @property
    def event_version(self) -> int: ...

    @property
    def routing_key(self) -> str: ...

    @property
    def idempotency_key(self) -> str: ...

    @property
    def correlation_id(self) -> UUID | None: ...

    @property
    def payload(self) -> dict[str, Any] | None: ...

    @property
    def status(self) -> str: ...


class OutboxEnvelopeValidationError(ValueError):
    pass


def validate_outbox_envelope(envelope: dict[str, Any]) -> None:
    missing = REQUIRED_ENVELOPE_FIELDS - set(envelope.keys())
    if missing:
        raise OutboxEnvelopeValidationError(
            f"Missing required envelope fields: {sorted(missing)}"
        )

    event_type = envelope.get("event_type", "")
    if not event_type or not isinstance(event_type, str):
        raise OutboxEnvelopeValidationError("event_type must be a non-empty string")

    event_version = envelope.get("event_version")
    if not isinstance(event_version, int) or event_version < 1:
        raise OutboxEnvelopeValidationError(
            f"event_version must be a positive integer, got: {event_version}"
        )

    routing_key = envelope.get("routing_key", "")
    if not routing_key or not isinstance(routing_key, str):
        raise OutboxEnvelopeValidationError("routing_key must be a non-empty string")
    segments = routing_key.split(".")
    if len(segments) < ROUTING_KEY_MIN_SEGMENTS:
        raise OutboxEnvelopeValidationError(
            f"routing_key must have at least {ROUTING_KEY_MIN_SEGMENTS} segments "
            f"(e.g. 'module.entity.action.v1'), got: '{routing_key}'"
        )

    idempotency_key = envelope.get("idempotency_key", "")
    if not idempotency_key or not isinstance(idempotency_key, str):
        raise OutboxEnvelopeValidationError(
            "idempotency_key must be a non-empty string"
        )

    correlation_id = envelope.get("correlation_id")
    if not correlation_id:
        raise OutboxEnvelopeValidationError(
            "correlation_id is required and must be non-empty"
        )

    producer_module = envelope.get("producer_module", "")
    if not producer_module or not isinstance(producer_module, str):
        raise OutboxEnvelopeValidationError(
            "producer_module must be a non-empty string"
        )

    occurred_at = envelope.get("occurred_at")
    if not occurred_at:
        raise OutboxEnvelopeValidationError(
            "occurred_at is required and must be non-empty"
        )
