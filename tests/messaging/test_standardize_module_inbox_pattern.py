"""Tests for spec 101 — standardize module inbox pattern."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
import uuid6

from shared.messaging.inbox_contracts import (
    REQUIRED_INBOX_ENVELOPE_FIELDS,
    InboxEnvelopeValidationError,
    InboxEventProtocol,
    validate_inbox_envelope,
)


def _valid_inbox_envelope() -> dict:
    return {
        "event_type": "agent.execution.completed.v1",
        "event_version": 1,
        "routing_key": "agent.execution.completed.v1",
        "idempotency_key": "idem-key-abc123",
        "correlation_id": str(uuid6.uuid7()),
        "producer_module": "agent",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {"agent_id": str(uuid6.uuid7())},
    }


class TestInboxPatternContractAcceptsValid:
    """Success: valid inbox envelope passes validation."""

    def test_valid_envelope_passes(self):
        envelope = _valid_inbox_envelope()
        validate_inbox_envelope(envelope)

    def test_valid_envelope_without_optional_fields(self):
        envelope = _valid_inbox_envelope()
        envelope.pop("causation_id", None)
        envelope.pop("headers", None)
        envelope.pop("metadata", None)
        validate_inbox_envelope(envelope)

    def test_valid_envelope_with_optional_fields(self):
        envelope = _valid_inbox_envelope()
        envelope["event_id"] = str(uuid6.uuid7())
        envelope["causation_id"] = str(uuid6.uuid7())
        envelope["headers"] = {"x-event-type": "agent.execution.completed.v1"}
        envelope["metadata"] = {"source": "test"}
        envelope["aggregate_type"] = "execution"
        envelope["aggregate_id"] = str(uuid6.uuid7())
        validate_inbox_envelope(envelope)

    def test_agent_inbox_model_satisfies_protocol(self):
        from modules.agent.infra.database.models import AgentInboxEventModel

        model = AgentInboxEventModel()
        model.message_id = "msg-123"
        model.producer_module = "billing"
        model.consumer_module = "agent"
        model.event_type = "billing.usage.recorded.v1"
        model.event_version = 1
        model.routing_key = "billing.usage.recorded.v1"
        model.idempotency_key = "key456"
        model.correlation_id = uuid6.uuid7()
        model.payload = {}
        model.status = "received"
        assert isinstance(model, InboxEventProtocol)

    def test_rabbit_message_to_inbox_produces_valid_envelope(self):
        from modules.agent.infra.messaging.event_mappers import rabbit_message_to_inbox

        class FakeMessage:
            body = b'{"event_type": "agent.execution.requested.v1", "event_version": 1, "routing_key": "agent.execution.requested.v1", "idempotency_key": "test-key", "correlation_id": "' + str(uuid6.uuid7()).encode() + b'", "producer_module": "agent", "occurred_at": "2026-06-14T00:00:00+00:00", "payload": {}}'
            routing_key = "agent.execution.requested.v1"
            correlation_id = str(uuid6.uuid7())
            headers = {"x-event-type": "agent.execution.requested.v1"}
            message_id = "msg-test-001"

        model = rabbit_message_to_inbox(FakeMessage())
        envelope = {
            "event_type": model.event_type,
            "event_version": model.event_version,
            "routing_key": model.routing_key,
            "idempotency_key": model.idempotency_key,
            "correlation_id": str(model.correlation_id),
            "producer_module": model.producer_module,
            "occurred_at": model.created_at.isoformat() if model.created_at else datetime.now(timezone.utc).isoformat(),
            "payload": model.payload,
        }
        validate_inbox_envelope(envelope)


class TestInboxPatternContractRejectsInvalid:
    """Failure: incomplete envelope, invalid routing key, or bad version rejected."""

    def test_missing_required_field_raises(self):
        for field in REQUIRED_INBOX_ENVELOPE_FIELDS:
            envelope = _valid_inbox_envelope()
            envelope.pop(field, None)
            with pytest.raises(InboxEnvelopeValidationError):
                validate_inbox_envelope(envelope)

    def test_empty_event_type_raises(self):
        envelope = _valid_inbox_envelope()
        envelope["event_type"] = ""
        with pytest.raises(InboxEnvelopeValidationError, match="event_type"):
            validate_inbox_envelope(envelope)

    def test_zero_event_version_raises(self):
        envelope = _valid_inbox_envelope()
        envelope["event_version"] = 0
        with pytest.raises(InboxEnvelopeValidationError, match="event_version"):
            validate_inbox_envelope(envelope)

    def test_negative_event_version_raises(self):
        envelope = _valid_inbox_envelope()
        envelope["event_version"] = -1
        with pytest.raises(InboxEnvelopeValidationError, match="event_version"):
            validate_inbox_envelope(envelope)

    def test_empty_routing_key_raises(self):
        envelope = _valid_inbox_envelope()
        envelope["routing_key"] = ""
        with pytest.raises(InboxEnvelopeValidationError, match="routing_key"):
            validate_inbox_envelope(envelope)

    def test_routing_key_too_few_segments_raises(self):
        envelope = _valid_inbox_envelope()
        envelope["routing_key"] = "agent.execution"
        with pytest.raises(InboxEnvelopeValidationError, match="routing_key"):
            validate_inbox_envelope(envelope)

    def test_empty_idempotency_key_raises(self):
        envelope = _valid_inbox_envelope()
        envelope["idempotency_key"] = ""
        with pytest.raises(InboxEnvelopeValidationError, match="idempotency_key"):
            validate_inbox_envelope(envelope)

    def test_empty_correlation_id_raises(self):
        envelope = _valid_inbox_envelope()
        envelope["correlation_id"] = ""
        with pytest.raises(InboxEnvelopeValidationError, match="correlation_id"):
            validate_inbox_envelope(envelope)

    def test_empty_producer_module_raises(self):
        envelope = _valid_inbox_envelope()
        envelope["producer_module"] = ""
        with pytest.raises(InboxEnvelopeValidationError, match="producer_module"):
            validate_inbox_envelope(envelope)

    def test_missing_occurred_at_raises(self):
        envelope = _valid_inbox_envelope()
        envelope["occurred_at"] = ""
        with pytest.raises(InboxEnvelopeValidationError, match="occurred_at"):
            validate_inbox_envelope(envelope)


class TestInboxPatternIdempotency:
    """Idempotency: same envelope validates repeatedly without side effects."""

    def test_same_envelope_validates_repeatedly(self):
        envelope = _valid_inbox_envelope()
        for _ in range(10):
            validate_inbox_envelope(envelope)

    def test_duplicate_message_id_implies_deduplication(self):
        from modules.agent.infra.database.models import AgentInboxEventModel

        constraints = AgentInboxEventModel.__table_args__
        constraint_names = [
            c.name for c in constraints if hasattr(c, "name") and c.name
        ]
        assert "uq_agent_inbox_message_id" in constraint_names

    def test_duplicate_idempotency_key_implies_deduplication(self):
        from modules.agent.infra.database.models import AgentInboxEventModel

        constraints = AgentInboxEventModel.__table_args__
        constraint_names = [
            c.name for c in constraints if hasattr(c, "name") and c.name
        ]
        assert "uq_agent_inbox_idempotency_key" in constraint_names
