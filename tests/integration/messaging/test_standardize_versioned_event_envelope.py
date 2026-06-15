"""Integration tests for spec 090 — standardize versioned event envelope.

Verifies that every module's domain events and use-case event_type strings
conform to the standard EventEnvelope contract defined in shared/messaging.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
import uuid6

from shared.messaging.event_envelope import (
    REQUIRED_ENVELOPE_FIELDS,
    EventEnvelope,
    EventEnvelopeValidationError,
    validate_event_envelope,
)


def test_all_required_envelope_fields_are_present():
    """Verify every field prescribed by spec 090 exists in REQUIRED_ENVELOPE_FIELDS."""
    expected = frozenset({
        "event_id",
        "event_type",
        "event_version",
        "occurred_at",
        "producer_module",
        "routing_key",
        "payload",
        "idempotency_key",
        "correlation_id",
    })
    missing = expected - REQUIRED_ENVELOPE_FIELDS
    extra = REQUIRED_ENVELOPE_FIELDS - expected
    assert not missing, f"Missing required fields: {missing}"
    assert not extra, f"Unexpected required fields: {extra}"


def test_event_envelope_dataclass_has_causation_id():
    """causation_id must be present (optional) on the EventEnvelope dataclass."""
    fields = {f.name for f in EventEnvelope.__dataclass_fields__.values()}
    assert "causation_id" in fields


def test_event_envelope_dataclass_has_traceparent():
    """traceparent / metadata must be present (optional) on the EventEnvelope."""
    fields = {f.name for f in EventEnvelope.__dataclass_fields__.values()}
    assert "metadata" in fields, "metadata field is the extensibility container for traceparent etc."


def test_valid_envelope_passes_validation():
    """A correctly-constructed envelope passes validate_event_envelope."""
    envelope = {
        "event_id": str(uuid6.uuid7()),
        "event_type": "identity.user.created.v1",
        "event_version": 1,
        "producer_module": "identity",
        "routing_key": "identity.user.created.v1",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {"user_id": str(uuid6.uuid7())},
        "idempotency_key": str(uuid6.uuid7()),
        "correlation_id": str(uuid6.uuid7()),
    }
    validate_event_envelope(envelope)


def test_envelope_missing_required_field_raises():
    """Omitting a required field raises EventEnvelopeValidationError."""
    envelope = {
        "event_id": str(uuid6.uuid7()),
        "event_type": "agent.execution_requested.v1",
        "event_version": 1,
        "producer_module": "agent",
        "routing_key": "agent.execution.requested.v1",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {},
        "idempotency_key": "key",
    }
    with pytest.raises(EventEnvelopeValidationError):
        validate_event_envelope(envelope)


def test_envelope_invalid_event_type_raises():
    """An unversioned event_type raises EventEnvelopeValidationError."""
    envelope = {
        "event_id": str(uuid6.uuid7()),
        "event_type": "agent.execution_requested",
        "event_version": 1,
        "producer_module": "agent",
        "routing_key": "agent.execution_requested",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {},
        "idempotency_key": "key",
        "correlation_id": str(uuid6.uuid7()),
    }
    with pytest.raises(EventEnvelopeValidationError):
        validate_event_envelope(envelope)


def test_envelope_version_mismatch_raises():
    """When event_type version suffix differs from event_version, validation fails."""
    envelope = {
        "event_id": str(uuid6.uuid7()),
        "event_type": "agent.execution_requested.v2",
        "event_version": 1,
        "producer_module": "agent",
        "routing_key": "agent.execution.requested.v2",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {},
        "idempotency_key": "key",
        "correlation_id": str(uuid6.uuid7()),
    }
    with pytest.raises(EventEnvelopeValidationError):
        validate_event_envelope(envelope)


def test_envelope_producer_mismatch_raises():
    """When event_type doesn't start with producer_module, validation fails."""
    envelope = {
        "event_id": str(uuid6.uuid7()),
        "event_type": "identity.user.created.v1",
        "event_version": 1,
        "producer_module": "agent",
        "routing_key": "identity.user.created.v1",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {},
        "idempotency_key": "key",
        "correlation_id": str(uuid6.uuid7()),
    }
    with pytest.raises(EventEnvelopeValidationError):
        validate_event_envelope(envelope)


def test_event_envelope_constructs_with_all_required_fields():
    """EventEnvelope dataclass can be instantiated with all required fields."""
    env = EventEnvelope(
        event_id=uuid6.uuid7(),
        event_type="core.project.created.v1",
        event_version=1,
        producer_module="core",
        routing_key="core.project.created.v1",
        occurred_at=datetime.now(timezone.utc),
        payload={"project_id": str(uuid6.uuid7())},
        idempotency_key=str(uuid6.uuid7()),
        correlation_id=uuid6.uuid7(),
    )
    assert env.event_type == "core.project.created.v1"


def test_event_envelope_constructs_with_optional_fields():
    """EventEnvelope dataclass accepts causation_id and metadata."""
    env = EventEnvelope(
        event_id=uuid6.uuid7(),
        event_type="billing.plan.created.v1",
        event_version=1,
        producer_module="billing",
        routing_key="billing.plan.created.v1",
        occurred_at=datetime.now(timezone.utc),
        payload={"plan_id": str(uuid6.uuid7())},
        idempotency_key=str(uuid6.uuid7()),
        correlation_id=uuid6.uuid7(),
        causation_id=uuid6.uuid7(),
        metadata={"traceparent": "00-abc123-xyz-01"},
    )
    assert env.causation_id is not None
    assert env.metadata["traceparent"] == "00-abc123-xyz-01"


def test_envelope_round_trip_dict():
    """An EventEnvelope can be serialized to dict and back via constructor."""
    env = EventEnvelope(
        event_id=uuid6.uuid7(),
        event_type="metering.usage.recorded.v1",
        event_version=1,
        producer_module="metering",
        routing_key="metering.usage.recorded.v1",
        occurred_at=datetime.now(timezone.utc),
        payload={"tokens": 150},
        idempotency_key=str(uuid6.uuid7()),
        correlation_id=uuid6.uuid7(),
    )
    as_dict = {
        "event_id": str(env.event_id),
        "event_type": env.event_type,
        "event_version": env.event_version,
        "producer_module": env.producer_module,
        "routing_key": env.routing_key,
        "occurred_at": env.occurred_at.isoformat(),
        "payload": env.payload,
        "idempotency_key": env.idempotency_key,
        "correlation_id": str(env.correlation_id),
    }
    validate_event_envelope(as_dict)


PARAM_VERSIONED_EVENT_TYPES = [
    "agent.execution.requested.v1",
    "agent.execution.completed.v1",
    "agent.execution.failed.v1",
    "agent.knowledge.document_indexed.v1",
    "agent.execution.fallback_triggered.v1",
]


@pytest.mark.parametrize("event_type", PARAM_VERSIONED_EVENT_TYPES)
def test_agent_versioned_event_types_pass_validation(event_type):
    """Every agent versioned domain event type passes the envelope validation."""
    envelope = {
        "event_id": str(uuid6.uuid7()),
        "event_type": event_type,
        "event_version": 1,
        "producer_module": "agent",
        "routing_key": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {},
        "idempotency_key": str(uuid6.uuid7()),
        "correlation_id": str(uuid6.uuid7()),
    }
    validate_event_envelope(envelope)
