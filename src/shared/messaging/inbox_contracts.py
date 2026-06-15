"""Standardized module inbox pattern contracts.

Every module that consumes events must conform to this contract:
1. Each module owns its Inbox table in its own schema/namespace.
2. The consumer persists the message to Inbox before acknowledging the broker.
3. Duplicates are resolved by unique constraints on `message_id` and `idempotency_key`.
4. The processor claims pending Inbox records, calls internal handlers, and updates
   only its own state within the same transaction.
5. The received envelope must contain all REQUIRED_INBOX_ENVELOPE_FIELDS.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import UUID


REQUIRED_INBOX_ENVELOPE_FIELDS: frozenset[str] = frozenset(
    [
        "event_type",
        "event_version",
        "routing_key",
        "idempotency_key",
        "correlation_id",
        "producer_module",
        "occurred_at",
        "payload",
    ]
)

OPTIONAL_INBOX_ENVELOPE_FIELDS: frozenset[str] = frozenset(
    [
        "event_id",
        "causation_id",
        "headers",
        "metadata",
        "aggregate_type",
        "aggregate_id",
    ]
)

ROUTING_KEY_MIN_SEGMENTS: int = 3


@runtime_checkable
class InboxEventProtocol(Protocol):
    @property
    def message_id(self) -> str: ...

    @property
    def producer_module(self) -> str: ...

    @property
    def consumer_module(self) -> str: ...

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


class InboxEnvelopeValidationError(ValueError):
    pass


def validate_inbox_envelope(envelope: dict[str, Any]) -> None:
    missing = REQUIRED_INBOX_ENVELOPE_FIELDS - set(envelope.keys())
    if missing:
        raise InboxEnvelopeValidationError(
            f"Missing required inbox envelope fields: {sorted(missing)}"
        )

    event_type = envelope.get("event_type", "")
    if not event_type or not isinstance(event_type, str):
        raise InboxEnvelopeValidationError("event_type must be a non-empty string")

    event_version = envelope.get("event_version")
    if not isinstance(event_version, int) or event_version < 1:
        raise InboxEnvelopeValidationError(
            f"event_version must be a positive integer, got: {event_version}"
        )

    routing_key = envelope.get("routing_key", "")
    if not routing_key or not isinstance(routing_key, str):
        raise InboxEnvelopeValidationError("routing_key must be a non-empty string")
    segments = routing_key.split(".")
    if len(segments) < ROUTING_KEY_MIN_SEGMENTS:
        raise InboxEnvelopeValidationError(
            f"routing_key must have at least {ROUTING_KEY_MIN_SEGMENTS} segments "
            f"(e.g. 'module.entity.action.v1'), got: '{routing_key}'"
        )

    idempotency_key = envelope.get("idempotency_key", "")
    if not idempotency_key or not isinstance(idempotency_key, str):
        raise InboxEnvelopeValidationError(
            "idempotency_key must be a non-empty string"
        )

    correlation_id = envelope.get("correlation_id")
    if not correlation_id:
        raise InboxEnvelopeValidationError(
            "correlation_id is required and must be non-empty"
        )

    producer_module = envelope.get("producer_module", "")
    if not producer_module or not isinstance(producer_module, str):
        raise InboxEnvelopeValidationError(
            "producer_module must be a non-empty string"
        )

    occurred_at = envelope.get("occurred_at")
    if not occurred_at:
        raise InboxEnvelopeValidationError(
            "occurred_at is required and must be non-empty"
        )
