"""Tests for spec 073 — create agent event mappers."""
import json
from dataclasses import dataclass
from typing import Any

import pytest
import uuid6

from modules.agent.domain.events import AgentExecutionRequestedV1
from modules.agent.infra.database.models import (
    AgentInboxEventModel,
    AgentOutboxEventModel,
)
from modules.agent.infra.messaging.event_mappers import (
    RabbitMQMessageEnvelope,
    domain_event_to_outbox,
    outbox_to_rabbit_message,
    rabbit_message_to_inbox,
)


@dataclass
class FakeIncomingMessage:
    body: bytes
    routing_key: str | None = None
    correlation_id: str | None = None
    headers: dict[str, Any] | None = None
    message_id: str | None = None


class TestDomainEventToOutbox:
    """Verify domain_event_to_outbox mapping."""

    def test_success_maps_all_fields(self):
        agent_id = uuid6.uuid7()
        session_id = uuid6.uuid7()
        event = AgentExecutionRequestedV1.create(
            agent_id=agent_id,
            session_id=session_id,
            payload={"agent_id": str(agent_id), "aggregate_type": "agent", "aggregate_id": str(agent_id)},
        )
        model = domain_event_to_outbox(event)
        assert isinstance(model, AgentOutboxEventModel)
        assert model.event_type == "agent.execution.requested.v1"
        assert model.event_version == 1
        assert model.routing_key == "agent.execution.requested.v1"
        assert model.idempotency_key == event.idempotency_key
        assert model.correlation_id == event.correlation_id
        assert model.status == "pending"
        assert model.attempts == 0

    def test_preserves_payload(self):
        payload = {"key": "value", "aggregate_type": "agent", "aggregate_id": str(uuid6.uuid7())}
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid6.uuid7(),
            session_id=uuid6.uuid7(),
            payload=payload,
        )
        model = domain_event_to_outbox(event)
        assert model.payload == payload

    def test_preserves_metadata(self):
        meta = {"trace_id": "abc123"}
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid6.uuid7(),
            session_id=uuid6.uuid7(),
            payload={},
            metadata=meta,
        )
        model = domain_event_to_outbox(event)
        assert model.metadata_ == meta

    def test_preserves_causation_id(self):
        causation = uuid6.uuid7()
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid6.uuid7(),
            session_id=uuid6.uuid7(),
            payload={},
            causation_id=causation,
        )
        model = domain_event_to_outbox(event)
        assert model.causation_id == causation


class TestDomainEventToOutboxValidation:
    """Verify mapper rejects invalid domain events."""

    def test_rejects_empty_routing_key(self):
        from modules.agent.domain.events import AgentDomainEvent
        with pytest.raises(ValueError, match="routing_key is required"):
            event = AgentDomainEvent(
                event_type="test.event",
                routing_key="valid.key",
                idempotency_key="k",
            )
            object.__setattr__(event, "routing_key", "")
            domain_event_to_outbox(event)

    def test_rejects_empty_idempotency_key(self):
        from modules.agent.domain.events import AgentDomainEvent
        with pytest.raises(ValueError, match="idempotency_key is required"):
            event = AgentDomainEvent(
                event_type="test.event",
                routing_key="valid.key",
                idempotency_key="k",
            )
            object.__setattr__(event, "idempotency_key", "")
            domain_event_to_outbox(event)

    def test_rejects_invalid_event_version(self):
        from modules.agent.domain.events import AgentDomainEvent
        with pytest.raises(ValueError, match="Invalid event_version"):
            event = AgentDomainEvent(
                event_type="test.event",
                routing_key="valid.key",
                idempotency_key="k",
            )
            object.__setattr__(event, "event_version", 0)
            domain_event_to_outbox(event)

    def test_rejects_none_correlation_id(self):
        from modules.agent.domain.events import AgentDomainEvent
        with pytest.raises(ValueError, match="correlation_id is required"):
            event = AgentDomainEvent(
                event_type="test.event",
                routing_key="valid.key",
                idempotency_key="k",
            )
            object.__setattr__(event, "correlation_id", None)
            domain_event_to_outbox(event)


class TestOutboxToRabbitMessage:
    """Verify outbox_to_rabbit_message mapping."""

    def _make_outbox_model(self) -> AgentOutboxEventModel:
        from datetime import datetime, timezone
        model = AgentOutboxEventModel()
        model.id = uuid6.uuid7()
        model.aggregate_type = "agent"
        model.aggregate_id = uuid6.uuid7()
        model.event_type = "agent.execution.requested.v1"
        model.event_version = 1
        model.routing_key = "agent.execution.requested.v1"
        model.payload = {"input": "hello"}
        model.metadata_ = {"trace": "t1"}
        model.idempotency_key = "idem-key-123"
        model.correlation_id = uuid6.uuid7()
        model.causation_id = uuid6.uuid7()
        model.status = "pending"
        model.attempts = 0
        model.created_at = datetime.now(timezone.utc)
        model.updated_at = datetime.now(timezone.utc)
        return model

    def test_success_returns_envelope(self):
        model = self._make_outbox_model()
        envelope = outbox_to_rabbit_message(model)
        assert isinstance(envelope, RabbitMQMessageEnvelope)
        assert envelope.routing_key == "agent.execution.requested.v1"
        assert envelope.correlation_id == str(model.correlation_id)

    def test_body_is_valid_json(self):
        model = self._make_outbox_model()
        envelope = outbox_to_rabbit_message(model)
        body = json.loads(envelope.body)
        assert body["event_type"] == "agent.execution.requested.v1"
        assert body["event_version"] == 1
        assert body["producer_module"] == "agent"
        assert body["routing_key"] == "agent.execution.requested.v1"
        assert body["payload"] == {"input": "hello"}
        assert body["idempotency_key"] == "idem-key-123"

    def test_headers_contain_metadata(self):
        model = self._make_outbox_model()
        envelope = outbox_to_rabbit_message(model)
        assert envelope.headers["x-event-type"] == "agent.execution.requested.v1"
        assert envelope.headers["x-event-version"] == "1"
        assert envelope.headers["x-producer-module"] == "agent"
        assert envelope.headers["x-idempotency-key"] == "idem-key-123"


class TestRabbitMessageToInbox:
    """Verify rabbit_message_to_inbox mapping."""

    def _make_incoming(self, payload: dict | None = None) -> FakeIncomingMessage:
        body_dict = {
            "event_id": str(uuid6.uuid7()),
            "event_type": "identity.user.created.v1",
            "event_version": 1,
            "producer_module": "identity",
            "routing_key": "identity.user.created.v1",
            "occurred_at": "2026-06-14T10:00:00+00:00",
            "payload": payload or {"user_id": str(uuid6.uuid7())},
            "idempotency_key": "idem-incoming-123",
            "correlation_id": str(uuid6.uuid7()),
            "causation_id": str(uuid6.uuid7()),
            "metadata": {},
        }
        return FakeIncomingMessage(
            body=json.dumps(body_dict).encode(),
            routing_key="identity.user.created.v1",
            correlation_id=body_dict["correlation_id"],
            headers={"x-event-type": "identity.user.created.v1"},
            message_id="msg-001",
        )

    def test_success_returns_inbox_model(self):
        msg = self._make_incoming()
        model = rabbit_message_to_inbox(msg)
        assert isinstance(model, AgentInboxEventModel)
        assert model.event_type == "identity.user.created.v1"
        assert model.event_version == 1
        assert model.producer_module == "identity"
        assert model.consumer_module == "agent"
        assert model.status == "received"
        assert model.message_id == "msg-001"

    def test_preserves_idempotency_key(self):
        msg = self._make_incoming()
        model = rabbit_message_to_inbox(msg)
        assert model.idempotency_key == "idem-incoming-123"

    def test_preserves_correlation_and_causation(self):
        msg = self._make_incoming()
        body = json.loads(msg.body)
        model = rabbit_message_to_inbox(msg)
        assert str(model.correlation_id) == body["correlation_id"]
        assert str(model.causation_id) == body["causation_id"]

    def test_rejects_missing_idempotency_key(self):
        body_dict = {
            "event_type": "test.event.v1",
            "event_version": 1,
            "routing_key": "test.event.v1",
            "idempotency_key": "",
            "correlation_id": str(uuid6.uuid7()),
            "payload": {},
        }
        msg = FakeIncomingMessage(
            body=json.dumps(body_dict).encode(),
            routing_key="test.event.v1",
            message_id="msg-bad",
        )
        with pytest.raises(ValueError, match="idempotency_key is required"):
            rabbit_message_to_inbox(msg)

    def test_rejects_invalid_event_version(self):
        body_dict = {
            "event_type": "test.event.v1",
            "event_version": 0,
            "routing_key": "test.event.v1",
            "idempotency_key": "key",
            "correlation_id": str(uuid6.uuid7()),
            "payload": {},
        }
        msg = FakeIncomingMessage(
            body=json.dumps(body_dict).encode(),
            routing_key="test.event.v1",
            message_id="msg-bad",
        )
        with pytest.raises(ValueError, match="Invalid event_version"):
            rabbit_message_to_inbox(msg)


class TestIdempotencyDeterminism:
    """Same domain event always produces same outbox idempotency_key."""

    def test_same_event_same_key(self):
        agent_id = uuid6.uuid7()
        session_id = uuid6.uuid7()
        e1 = AgentExecutionRequestedV1.create(
            agent_id=agent_id, session_id=session_id, payload={}
        )
        e2 = AgentExecutionRequestedV1.create(
            agent_id=agent_id, session_id=session_id, payload={}
        )
        m1 = domain_event_to_outbox(e1)
        m2 = domain_event_to_outbox(e2)
        assert m1.idempotency_key == m2.idempotency_key


class TestConcurrencySupport:
    """Verify mapper output is compatible with outbox unique constraint."""

    def test_outbox_unique_constraint_on_idempotency_key(self):
        from sqlalchemy import UniqueConstraint as UC
        table = AgentOutboxEventModel.__table__
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "idempotency_key" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1

    def test_inbox_unique_constraint_on_message_id(self):
        from sqlalchemy import UniqueConstraint as UC
        table = AgentInboxEventModel.__table__
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "message_id" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1
