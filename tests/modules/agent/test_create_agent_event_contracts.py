"""Tests for spec 072 — create agent event contracts."""
import pytest
import uuid6

from modules.agent.domain.events import (
    AgentDomainEvent,
    AgentExecutionCompletedV1,
    AgentExecutionFailedV1,
    AgentExecutionRequestedV1,
    AgentFallbackTriggeredV1,
    AgentKnowledgeDocumentIndexedV1,
)


class TestAgentDomainEventEnvelope:
    """Verify base envelope contract has all required fields."""

    REQUIRED_FIELDS = [
        "event_id",
        "event_type",
        "event_version",
        "producer_module",
        "routing_key",
        "occurred_at",
        "payload",
        "idempotency_key",
        "correlation_id",
        "causation_id",
        "metadata",
    ]

    def test_all_envelope_fields_present(self):
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(AgentDomainEvent)}
        for required in self.REQUIRED_FIELDS:
            assert required in field_names, f"Missing envelope field: {required}"

    def test_missing_event_type_raises(self):
        with pytest.raises(ValueError, match="event_type is required"):
            AgentDomainEvent(
                event_type="",
                routing_key="test.routing.key",
                idempotency_key="test-key",
            )

    def test_missing_routing_key_raises(self):
        with pytest.raises(ValueError, match="routing_key is required"):
            AgentDomainEvent(
                event_type="test.event",
                routing_key="",
                idempotency_key="test-key",
            )

    def test_missing_idempotency_key_raises(self):
        with pytest.raises(ValueError, match="idempotency_key is required"):
            AgentDomainEvent(
                event_type="test.event",
                routing_key="test.routing.key",
                idempotency_key="",
            )

    def test_producer_module_is_agent(self):
        event = AgentDomainEvent(
            event_type="test.event",
            routing_key="test.key",
            idempotency_key="k",
        )
        assert event.producer_module == "agent"


class TestAgentExecutionRequestedV1:
    """Verify AgentExecutionRequestedV1 contract."""

    def test_event_type(self):
        agent_id = uuid6.uuid7()
        session_id = uuid6.uuid7()
        event = AgentExecutionRequestedV1.create(
            agent_id=agent_id,
            session_id=session_id,
            payload={"input": "hello"},
        )
        assert event.event_type == "agent.execution.requested.v1"

    def test_routing_key(self):
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid6.uuid7(),
            session_id=uuid6.uuid7(),
            payload={},
        )
        assert event.routing_key == "agent.execution.requested.v1"

    def test_event_version(self):
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid6.uuid7(),
            session_id=uuid6.uuid7(),
            payload={},
        )
        assert event.event_version == 1

    def test_producer_module(self):
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid6.uuid7(),
            session_id=uuid6.uuid7(),
            payload={},
        )
        assert event.producer_module == "agent"

    def test_payload_preserved(self):
        payload = {"input": "test", "agent_id": "abc"}
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid6.uuid7(),
            session_id=uuid6.uuid7(),
            payload=payload,
        )
        assert event.payload == payload


class TestAgentExecutionCompletedV1:
    """Verify AgentExecutionCompletedV1 contract."""

    def test_event_type(self):
        event = AgentExecutionCompletedV1.create(
            agent_id=uuid6.uuid7(),
            session_id=uuid6.uuid7(),
            payload={"output": "done"},
        )
        assert event.event_type == "agent.execution.completed.v1"

    def test_routing_key(self):
        event = AgentExecutionCompletedV1.create(
            agent_id=uuid6.uuid7(),
            session_id=uuid6.uuid7(),
            payload={},
        )
        assert event.routing_key == "agent.execution.completed.v1"


class TestAgentExecutionFailedV1:
    """Verify AgentExecutionFailedV1 contract."""

    def test_event_type(self):
        event = AgentExecutionFailedV1.create(
            agent_id=uuid6.uuid7(),
            session_id=uuid6.uuid7(),
            payload={"error": "timeout"},
        )
        assert event.event_type == "agent.execution.failed.v1"

    def test_routing_key(self):
        event = AgentExecutionFailedV1.create(
            agent_id=uuid6.uuid7(),
            session_id=uuid6.uuid7(),
            payload={},
        )
        assert event.routing_key == "agent.execution.failed.v1"


class TestAgentKnowledgeDocumentIndexedV1:
    """Verify AgentKnowledgeDocumentIndexedV1 contract."""

    def test_event_type(self):
        event = AgentKnowledgeDocumentIndexedV1.create(
            document_id=uuid6.uuid7(),
            collection_id=uuid6.uuid7(),
            payload={"chunks": 10},
        )
        assert event.event_type == "agent.knowledge.document_indexed.v1"

    def test_routing_key(self):
        event = AgentKnowledgeDocumentIndexedV1.create(
            document_id=uuid6.uuid7(),
            collection_id=uuid6.uuid7(),
            payload={},
        )
        assert event.routing_key == "agent.knowledge.document_indexed.v1"


class TestAgentFallbackTriggeredV1:
    """Verify AgentFallbackTriggeredV1 contract."""

    def test_event_type(self):
        event = AgentFallbackTriggeredV1.create(
            agent_id=uuid6.uuid7(),
            session_id=uuid6.uuid7(),
            payload={"reason": "primary_unavailable"},
        )
        assert event.event_type == "agent.execution.fallback_triggered.v1"

    def test_routing_key(self):
        event = AgentFallbackTriggeredV1.create(
            agent_id=uuid6.uuid7(),
            session_id=uuid6.uuid7(),
            payload={},
        )
        assert event.routing_key == "agent.execution.fallback_triggered.v1"


class TestIdempotencyKeyDeterminism:
    """Verify idempotency_key is deterministic: same inputs produce same key."""

    def test_same_inputs_produce_same_key(self):
        agent_id = uuid6.uuid7()
        session_id = uuid6.uuid7()
        event_a = AgentExecutionRequestedV1.create(
            agent_id=agent_id,
            session_id=session_id,
            payload={"x": 1},
        )
        event_b = AgentExecutionRequestedV1.create(
            agent_id=agent_id,
            session_id=session_id,
            payload={"x": 2},
        )
        assert event_a.idempotency_key == event_b.idempotency_key

    def test_different_inputs_produce_different_key(self):
        agent_id = uuid6.uuid7()
        session_a = uuid6.uuid7()
        session_b = uuid6.uuid7()
        event_a = AgentExecutionRequestedV1.create(
            agent_id=agent_id,
            session_id=session_a,
            payload={},
        )
        event_b = AgentExecutionRequestedV1.create(
            agent_id=agent_id,
            session_id=session_b,
            payload={},
        )
        assert event_a.idempotency_key != event_b.idempotency_key

    def test_different_event_types_produce_different_key(self):
        agent_id = uuid6.uuid7()
        session_id = uuid6.uuid7()
        event_a = AgentExecutionRequestedV1.create(
            agent_id=agent_id,
            session_id=session_id,
            payload={},
        )
        event_b = AgentExecutionCompletedV1.create(
            agent_id=agent_id,
            session_id=session_id,
            payload={},
        )
        assert event_a.idempotency_key != event_b.idempotency_key

    def test_compute_idempotency_key_is_sha256(self):
        key = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=uuid6.uuid7(),
            event_type="test",
            discriminator="d",
        )
        assert len(key) == 64
        int(key, 16)


class TestConcurrencyIdempotencyKeyUniqueness:
    """Verify that idempotency_key uniqueness supports concurrency safety.

    Two events from the same logical operation produce the same key,
    so the Outbox unique constraint prevents double-write.
    """

    def test_outbox_model_has_idempotency_key_unique(self):
        from modules.agent.infra.database.models import AgentOutboxEventModel
        from sqlalchemy import UniqueConstraint as UC
        table = AgentOutboxEventModel.__table__
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "idempotency_key" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1

    def test_two_events_same_operation_same_key(self):
        agent_id = uuid6.uuid7()
        session_id = uuid6.uuid7()
        e1 = AgentExecutionRequestedV1.create(
            agent_id=agent_id, session_id=session_id, payload={}
        )
        e2 = AgentExecutionRequestedV1.create(
            agent_id=agent_id, session_id=session_id, payload={}
        )
        assert e1.idempotency_key == e2.idempotency_key
