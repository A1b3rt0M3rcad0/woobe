"""Tests for spec 100 — standardize module outbox pattern."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import uuid6

from shared.messaging.outbox_contracts import (
    REQUIRED_ENVELOPE_FIELDS,
    OutboxEnvelopeValidationError,
    OutboxEventProtocol,
    validate_outbox_envelope,
)


def _valid_envelope() -> dict:
    return {
        "event_id": str(uuid6.uuid7()),
        "event_type": "agent.execution.requested.v1",
        "event_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer_module": "agent",
        "routing_key": "agent.execution.requested.v1",
        "payload": {"agent_id": str(uuid6.uuid7())},
        "idempotency_key": "abc123hash",
        "correlation_id": str(uuid6.uuid7()),
        "causation_id": str(uuid6.uuid7()),
        "metadata": {},
    }


class TestOutboxPatternContractAcceptsValid:
    """Success: valid envelope passes validation."""

    def test_valid_envelope_passes(self):
        envelope = _valid_envelope()
        validate_outbox_envelope(envelope)

    def test_valid_envelope_without_optional_fields(self):
        envelope = _valid_envelope()
        envelope.pop("causation_id", None)
        envelope.pop("metadata", None)
        validate_outbox_envelope(envelope)

    def test_valid_envelope_with_aggregate_fields(self):
        envelope = _valid_envelope()
        envelope["aggregate_type"] = "agent"
        envelope["aggregate_id"] = str(uuid6.uuid7())
        validate_outbox_envelope(envelope)

    def test_agent_outbox_model_satisfies_protocol(self):
        from modules.agent.infra.database.models import AgentOutboxEventModel

        model = AgentOutboxEventModel()
        model.event_type = "agent.test.v1"
        model.event_version = 1
        model.routing_key = "agent.test.v1"
        model.idempotency_key = "key123"
        model.correlation_id = uuid6.uuid7()
        model.payload = {}
        model.status = "pending"
        assert isinstance(model, OutboxEventProtocol)

    def test_agent_envelope_from_event_mappers_validates(self):
        from modules.agent.infra.database.models import AgentOutboxEventModel
        from modules.agent.infra.messaging.event_mappers import outbox_to_rabbit_message

        model = AgentOutboxEventModel()
        model.id = uuid6.uuid7()
        model.aggregate_type = "agent"
        model.aggregate_id = uuid6.uuid7()
        model.event_type = "agent.execution.requested.v1"
        model.event_version = 1
        model.routing_key = "agent.execution.requested.v1"
        model.payload = {"agent_id": str(uuid6.uuid7())}
        model.metadata_ = {}
        model.idempotency_key = "test-key-hash"
        model.correlation_id = uuid6.uuid7()
        model.causation_id = uuid6.uuid7()
        model.status = "publishing"
        model.created_at = datetime.now(timezone.utc)

        envelope_msg = outbox_to_rabbit_message(model)
        body = json.loads(envelope_msg.body)
        validate_outbox_envelope(body)


class TestOutboxPatternContractRejectsInvalid:
    """Failure: incomplete envelope, invalid routing key, or bad version rejected."""

    def test_missing_required_field_raises(self):
        for field in REQUIRED_ENVELOPE_FIELDS:
            envelope = _valid_envelope()
            envelope.pop(field, None)
            with pytest.raises(OutboxEnvelopeValidationError):
                validate_outbox_envelope(envelope)

    def test_empty_event_type_raises(self):
        envelope = _valid_envelope()
        envelope["event_type"] = ""
        with pytest.raises(OutboxEnvelopeValidationError, match="event_type"):
            validate_outbox_envelope(envelope)

    def test_zero_event_version_raises(self):
        envelope = _valid_envelope()
        envelope["event_version"] = 0
        with pytest.raises(OutboxEnvelopeValidationError, match="event_version"):
            validate_outbox_envelope(envelope)

    def test_negative_event_version_raises(self):
        envelope = _valid_envelope()
        envelope["event_version"] = -1
        with pytest.raises(OutboxEnvelopeValidationError, match="event_version"):
            validate_outbox_envelope(envelope)

    def test_empty_routing_key_raises(self):
        envelope = _valid_envelope()
        envelope["routing_key"] = ""
        with pytest.raises(OutboxEnvelopeValidationError, match="routing_key"):
            validate_outbox_envelope(envelope)

    def test_routing_key_too_few_segments_raises(self):
        envelope = _valid_envelope()
        envelope["routing_key"] = "agent.execution"
        with pytest.raises(OutboxEnvelopeValidationError, match="routing_key"):
            validate_outbox_envelope(envelope)

    def test_empty_idempotency_key_raises(self):
        envelope = _valid_envelope()
        envelope["idempotency_key"] = ""
        with pytest.raises(OutboxEnvelopeValidationError, match="idempotency_key"):
            validate_outbox_envelope(envelope)

    def test_empty_correlation_id_raises(self):
        envelope = _valid_envelope()
        envelope["correlation_id"] = ""
        with pytest.raises(OutboxEnvelopeValidationError, match="correlation_id"):
            validate_outbox_envelope(envelope)

    def test_empty_producer_module_raises(self):
        envelope = _valid_envelope()
        envelope["producer_module"] = ""
        with pytest.raises(OutboxEnvelopeValidationError, match="producer_module"):
            validate_outbox_envelope(envelope)

    def test_missing_occurred_at_raises(self):
        envelope = _valid_envelope()
        envelope["occurred_at"] = ""
        with pytest.raises(OutboxEnvelopeValidationError, match="occurred_at"):
            validate_outbox_envelope(envelope)


class TestOutboxPatternIdempotency:
    """Idempotency: same idempotency_key must produce the same validation result."""

    def test_same_envelope_validates_repeatedly(self):
        envelope = _valid_envelope()
        for _ in range(10):
            validate_outbox_envelope(envelope)

    def test_idempotency_key_deterministic_for_same_inputs(self):
        from modules.agent.domain.events import AgentDomainEvent

        agent_id = uuid6.uuid7()
        key1 = AgentDomainEvent.compute_idempotency_key(
            "agent", agent_id, "agent.execution.requested.v1", "disc"
        )
        key2 = AgentDomainEvent.compute_idempotency_key(
            "agent", agent_id, "agent.execution.requested.v1", "disc"
        )
        assert key1 == key2
        assert len(key1) > 0

    def test_different_discriminator_produces_different_key(self):
        from modules.agent.domain.events import AgentDomainEvent

        agent_id = uuid6.uuid7()
        key1 = AgentDomainEvent.compute_idempotency_key(
            "agent", agent_id, "agent.execution.requested.v1", "disc1"
        )
        key2 = AgentDomainEvent.compute_idempotency_key(
            "agent", agent_id, "agent.execution.requested.v1", "disc2"
        )
        assert key1 != key2
