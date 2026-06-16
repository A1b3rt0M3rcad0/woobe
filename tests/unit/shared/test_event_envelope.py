"""Unit tests for the IntegrationEvent envelope and serializer."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
import uuid6

from shared.messaging.event_envelope import (
    EventSerializer,
    IntegrationEvent,
    validate_event_envelope,
)

VALID_EVENT_TYPE = "agent.execution.completed.v1"


@pytest.fixture
def valid_event() -> IntegrationEvent:
    return IntegrationEvent(
        event_type=VALID_EVENT_TYPE,
        producer_module="agent",
        routing_key=VALID_EVENT_TYPE,
        idempotency_key=IntegrationEvent.compute_idempotency_key(
            "agent", uuid6.uuid7(), VALID_EVENT_TYPE
        ),
    )


class TestIntegrationEventCreation:
    def test_defaults(self, valid_event: IntegrationEvent):
        assert isinstance(valid_event.event_id, UUID)
        assert valid_event.event_version == 1
        assert isinstance(valid_event.occurred_at, datetime)
        assert isinstance(valid_event.correlation_id, UUID)
        assert valid_event.payload == {}
        assert valid_event.metadata == {}

    def test_custom_fields(self):
        event_id = uuid6.uuid7()
        correlation_id = uuid6.uuid7()
        causation_id = uuid6.uuid7()
        occurred = datetime.now(timezone.utc)
        event = IntegrationEvent(
            event_id=event_id,
            event_type=VALID_EVENT_TYPE,
            event_version=2,
            producer_module="agent",
            routing_key=VALID_EVENT_TYPE,
            occurred_at=occurred,
            payload={"key": "value"},
            idempotency_key="custom-key",
            correlation_id=correlation_id,
            causation_id=causation_id,
            metadata={"version": "2.0"},
            aggregate_type="agent",
            aggregate_id=uuid6.uuid7(),
        )
        assert event.event_id == event_id
        assert event.event_version == 2
        assert event.causation_id == causation_id
        assert event.aggregate_type == "agent"


class TestEventSerializer:
    def test_to_dict_types(self, valid_event: IntegrationEvent):
        data = EventSerializer.to_dict(valid_event)
        assert isinstance(data["event_id"], str)
        assert isinstance(data["event_type"], str)
        assert isinstance(data["event_version"], int)
        assert isinstance(data["occurred_at"], str)
        assert isinstance(data["payload"], dict)
        assert isinstance(data["idempotency_key"], str)
        assert isinstance(data["correlation_id"], str)

    def test_from_dict_optional_fields(self):
        data = {
            "event_id": str(uuid6.uuid7()),
            "event_type": VALID_EVENT_TYPE,
            "event_version": 1,
            "producer_module": "agent",
            "routing_key": VALID_EVENT_TYPE,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {},
            "idempotency_key": "key",
            "correlation_id": str(uuid6.uuid7()),
        }
        event = EventSerializer.from_dict(data)
        assert event.causation_id is None
        assert event.aggregate_type is None
        assert event.aggregate_id is None
        assert event.metadata == {}

    def test_validate_dict_valid(self, valid_event: IntegrationEvent):
        data = EventSerializer.to_dict(valid_event)
        validate_event_envelope(data)

    def test_validate_dict_invalid(self):
        with pytest.raises(Exception):
            EventSerializer.validate_dict({"bad": "data"})

    def test_json_preserves_types(self, valid_event: IntegrationEvent):
        raw = EventSerializer.to_json(valid_event)
        restored = EventSerializer.from_json(raw)
        assert restored.event_id == valid_event.event_id
        assert restored.event_version == valid_event.event_version
        assert restored.routing_key == valid_event.routing_key
