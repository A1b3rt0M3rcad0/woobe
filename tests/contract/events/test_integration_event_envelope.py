"""Contract tests for the canonical IntegrationEvent envelope.

Covers: round trip, invalid event, idempotency, version compatibility, redaction.
"""
from __future__ import annotations

from datetime import datetime, timezone


import pytest
import uuid6

from shared.messaging.event_envelope import (
    EVENT_TYPE_PATTERN,
    ROUTING_KEY_PATTERN,
    EventEnvelopeValidationError,
    EventSerializer,
    IntegrationEvent,
    validate_event_envelope,
)

VALID_EVENT_TYPE = "agent.execution.completed.v1"
VALID_ROUTING_KEY = "agent.execution.completed.v1"
VALID_PRODUCER = "agent"


def _make_valid_event(**overrides: object) -> IntegrationEvent:
    kwargs: dict = {
        "event_type": VALID_EVENT_TYPE,
        "producer_module": VALID_PRODUCER,
        "routing_key": VALID_ROUTING_KEY,
        "idempotency_key": IntegrationEvent.compute_idempotency_key(
            "agent", uuid6.uuid7(), VALID_EVENT_TYPE
        ),
    }
    kwargs.update(overrides)
    return IntegrationEvent(**kwargs)


class TestIntegrationEventRoundTrip:
    def test_create_valid_event(self):
        event = _make_valid_event()
        assert event.event_type == VALID_EVENT_TYPE
        assert event.producer_module == VALID_PRODUCER
        assert event.routing_key == VALID_ROUTING_KEY
        assert event.event_version == 1

    def test_serialize_deserialize_round_trip(self):
        original = _make_valid_event(payload={"agent_id": "abc", "session_id": "def"})
        data = EventSerializer.to_dict(original)
        restored = EventSerializer.from_dict(data)
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type
        assert restored.event_version == original.event_version
        assert restored.producer_module == original.producer_module
        assert restored.routing_key == original.routing_key
        assert restored.payload == original.payload
        assert restored.idempotency_key == original.idempotency_key
        assert restored.correlation_id == original.correlation_id
        assert restored.causation_id == original.causation_id

    def test_json_round_trip(self):
        original = _make_valid_event(payload={"key": "value"})
        raw = EventSerializer.to_json(original)
        restored = EventSerializer.from_json(raw)
        assert restored.event_id == original.event_id
        assert restored.payload == original.payload

    def test_to_envelope_round_trip(self):
        original = _make_valid_event()
        envelope = original.to_envelope()
        restored = IntegrationEvent.from_envelope(envelope)
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type


class TestIntegrationEventInvalid:
    def test_empty_event_type_raises(self):
        with pytest.raises(ValueError, match="event_type is required"):
            IntegrationEvent(event_type="", producer_module="agent", routing_key="agent.test.v1", idempotency_key="x")

    def test_empty_producer_raises(self):
        with pytest.raises(ValueError, match="producer_module is required"):
            IntegrationEvent(event_type="agent.test.v1", producer_module="", routing_key="agent.test.v1", idempotency_key="x")

    def test_empty_routing_key_raises(self):
        with pytest.raises(ValueError, match="routing_key is required"):
            IntegrationEvent(event_type="agent.test.v1", producer_module="agent", routing_key="", idempotency_key="x")

    def test_empty_idempotency_key_raises(self):
        with pytest.raises(ValueError, match="idempotency_key is required"):
            IntegrationEvent(event_type="agent.test.v1", producer_module="agent", routing_key="agent.test.v1", idempotency_key="")

    def test_validate_envelope_missing_fields(self):
        with pytest.raises(EventEnvelopeValidationError, match="Missing required"):
            validate_event_envelope({"event_type": "agent.test.v1"})

    def test_validate_envelope_bad_event_type(self):
        data = {
            "event_id": str(uuid6.uuid7()),
            "event_type": "no-version",
            "event_version": 1,
            "producer_module": "agent",
            "routing_key": "agent.test.v1",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {},
            "idempotency_key": "x",
            "correlation_id": str(uuid6.uuid7()),
        }
        with pytest.raises(EventEnvelopeValidationError, match="event_type must match"):
            validate_event_envelope(data)


class TestIntegrationEventIdempotency:
    def test_deterministic_key(self):
        agg_id = uuid6.uuid7()
        key1 = IntegrationEvent.compute_idempotency_key("agent", agg_id, "agent.execution.completed.v1", "session-1")
        key2 = IntegrationEvent.compute_idempotency_key("agent", agg_id, "agent.execution.completed.v1", "session-1")
        assert key1 == key2
        assert len(key1) == 64

    def test_different_discriminator_different_key(self):
        agg_id = uuid6.uuid7()
        key1 = IntegrationEvent.compute_idempotency_key("agent", agg_id, "agent.execution.completed.v1", "session-a")
        key2 = IntegrationEvent.compute_idempotency_key("agent", agg_id, "agent.execution.completed.v1", "session-b")
        assert key1 != key2


class TestIntegrationEventVersionCompatibility:
    def test_event_type_pattern_valid(self):
        assert EVENT_TYPE_PATTERN.match("agent.execution.completed.v1")
        assert EVENT_TYPE_PATTERN.match("billing.plan.created.v2")
        assert EVENT_TYPE_PATTERN.match("metering.usage.recorded.v10")

    def test_event_type_pattern_invalid(self):
        assert not EVENT_TYPE_PATTERN.match("no-version")
        assert not EVENT_TYPE_PATTERN.match("agent.event")
        assert not EVENT_TYPE_PATTERN.match("UPPERCASE.v1")

    def test_routing_key_pattern_valid(self):
        assert ROUTING_KEY_PATTERN.match("agent.execution.completed.v1")
        assert ROUTING_KEY_PATTERN.match("billing.plan.created")

    def test_routing_key_pattern_invalid(self):
        assert not ROUTING_KEY_PATTERN.match("agent.event")
        assert not ROUTING_KEY_PATTERN.match("short")


class TestIntegrationEventRedaction:
    def test_payload_excludes_sensitive_data(self):
        event = _make_valid_event(payload={
            "execution_id": str(uuid6.uuid7()),
            "token_count": 150,
        })
        data = EventSerializer.to_dict(event)
        assert "secret" not in data["payload"]
        assert "password" not in data["payload"]
        assert "api_key" not in data["payload"]

    def test_message_id_is_event_id(self):
        event = _make_valid_event()
        assert event.message_id == str(event.event_id)


class TestIntegrationEventCausation:
    def test_causation_chain_preserved(self):
        correlation_id = uuid6.uuid7()
        parent_event = _make_valid_event(
            event_type="agent.execution.requested.v1",
            correlation_id=correlation_id,
        )
        child_event = _make_valid_event(
            event_type="agent.execution.completed.v1",
            correlation_id=correlation_id,
            causation_id=parent_event.event_id,
        )
        assert child_event.causation_id == parent_event.event_id
        assert child_event.correlation_id == correlation_id
        data = EventSerializer.to_dict(child_event)
        restored = EventSerializer.from_dict(data)
        assert restored.causation_id == parent_event.event_id
