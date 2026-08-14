"""Tests for spec 102 — standardize event envelope."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
import uuid6

from shared.messaging.event_envelope import (
    EVENT_TYPE_PATTERN,
    REQUIRED_ENVELOPE_FIELDS,
    ROUTING_KEY_PATTERN,
    EventEnvelope,
    EventEnvelopeValidationError,
    validate_event_envelope,
)


def _valid_envelope() -> dict:
    return {
        "event_id": str(uuid6.uuid7()),
        "event_type": "agent.execution_requested.v1",
        "event_version": 1,
        "producer_module": "agent",
        "routing_key": "agent.execution.requested.v1",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {"agent_id": str(uuid6.uuid7())},
        "idempotency_key": "abc123hash",
        "correlation_id": str(uuid6.uuid7()),
    }


class TestEventEnvelopeAcceptsValid:
    """Success: valid envelope passes validation."""

    def test_valid_envelope_passes(self):
        envelope = _valid_envelope()
        validate_event_envelope(envelope)

    def test_valid_envelope_with_optional_fields(self):
        envelope = _valid_envelope()
        envelope["causation_id"] = str(uuid6.uuid7())
        envelope["metadata"] = {"source": "test"}
        envelope["aggregate_type"] = "execution"
        envelope["aggregate_id"] = str(uuid6.uuid7())
        validate_event_envelope(envelope)

    def test_valid_envelope_with_v2_version(self):
        envelope = _valid_envelope()
        envelope["event_type"] = "agent.execution_requested.v2"
        envelope["event_version"] = 2
        validate_event_envelope(envelope)

    def test_event_type_pattern_matches_valid_types(self):
        valid_types = [
            "agent.execution_requested.v1",
            "billing.usage_recorded.v1",
            "identity.workspace_created.v3",
            "agent.ask_job.completed.v1",
            "metering.token_usage.recorded.v2",
        ]
        for t in valid_types:
            assert EVENT_TYPE_PATTERN.match(t), f"Should match: {t}"

    def test_event_type_pattern_rejects_invalid_types(self):
        invalid_types = [
            "Agent.execution.v1",
            "agent",
            "agent.v1",
            "agent.execution",
            ".agent.execution.v1",
            "agent..execution.v1",
            "agent.Execution.v1",
        ]
        for t in invalid_types:
            assert not EVENT_TYPE_PATTERN.match(t), f"Should not match: {t}"

    def test_routing_key_pattern_matches_valid_keys(self):
        valid_keys = [
            "agent.execution.requested.v1",
            "billing.usage.recorded",
            "identity.workspace.created.v1",
        ]
        for k in valid_keys:
            assert ROUTING_KEY_PATTERN.match(k), f"Should match: {k}"

    def test_routing_key_pattern_rejects_invalid_keys(self):
        invalid_keys = [
            "agent.execution",
            "agent",
            ".agent.execution.requested",
            "Agent.execution.requested",
        ]
        for k in invalid_keys:
            assert not ROUTING_KEY_PATTERN.match(k), f"Should not match: {k}"

    def test_dataclass_envelope_creation(self):
        now = datetime.now(timezone.utc)
        uid = uuid6.uuid7()
        env = EventEnvelope(
            event_id=uid,
            event_type="agent.execution_requested.v1",
            event_version=1,
            producer_module="agent",
            routing_key="agent.execution.requested.v1",
            occurred_at=now,
            payload={"key": "value"},
            idempotency_key="test-key",
            correlation_id=uid,
        )
        assert env.event_type == "agent.execution_requested.v1"
        assert env.causation_id is None
        assert env.metadata == {}


class TestEventEnvelopeRejectsInvalid:
    """Failure: incomplete envelope, invalid format, or version mismatch rejected."""

    def test_missing_required_field_raises(self):
        for field_name in REQUIRED_ENVELOPE_FIELDS:
            envelope = _valid_envelope()
            envelope.pop(field_name, None)
            with pytest.raises(EventEnvelopeValidationError):
                validate_event_envelope(envelope)

    def test_invalid_event_type_format_raises(self):
        envelope = _valid_envelope()
        envelope["event_type"] = "AgentExecution"
        with pytest.raises(EventEnvelopeValidationError, match="event_type.*pattern"):
            validate_event_envelope(envelope)

    def test_event_type_without_version_suffix_raises(self):
        envelope = _valid_envelope()
        envelope["event_type"] = "agent.execution"
        with pytest.raises(EventEnvelopeValidationError, match="event_type.*pattern"):
            validate_event_envelope(envelope)

    def test_event_version_mismatch_raises(self):
        envelope = _valid_envelope()
        envelope["event_type"] = "agent.execution_requested.v1"
        envelope["event_version"] = 2
        with pytest.raises(EventEnvelopeValidationError, match="version suffix"):
            validate_event_envelope(envelope)

    def test_zero_event_version_raises(self):
        envelope = _valid_envelope()
        envelope["event_version"] = 0
        with pytest.raises(EventEnvelopeValidationError, match="event_version"):
            validate_event_envelope(envelope)

    def test_invalid_routing_key_format_raises(self):
        envelope = _valid_envelope()
        envelope["routing_key"] = "INVALID"
        with pytest.raises(EventEnvelopeValidationError, match="routing_key.*pattern"):
            validate_event_envelope(envelope)

    def test_routing_key_too_few_segments_raises(self):
        envelope = _valid_envelope()
        envelope["routing_key"] = "agent.execution"
        with pytest.raises(EventEnvelopeValidationError, match="routing_key.*pattern"):
            validate_event_envelope(envelope)

    def test_producer_module_mismatch_raises(self):
        envelope = _valid_envelope()
        envelope["producer_module"] = "billing"
        with pytest.raises(EventEnvelopeValidationError, match="producer_module prefix"):
            validate_event_envelope(envelope)

    def test_empty_idempotency_key_raises(self):
        envelope = _valid_envelope()
        envelope["idempotency_key"] = ""
        with pytest.raises(EventEnvelopeValidationError, match="idempotency_key"):
            validate_event_envelope(envelope)

    def test_empty_correlation_id_raises(self):
        envelope = _valid_envelope()
        envelope["correlation_id"] = ""
        with pytest.raises(EventEnvelopeValidationError, match="correlation_id"):
            validate_event_envelope(envelope)

    def test_empty_occurred_at_raises(self):
        envelope = _valid_envelope()
        envelope["occurred_at"] = ""
        with pytest.raises(EventEnvelopeValidationError, match="occurred_at"):
            validate_event_envelope(envelope)

    def test_payload_non_dict_raises(self):
        envelope = _valid_envelope()
        envelope["payload"] = "not a dict"
        with pytest.raises(EventEnvelopeValidationError, match="payload"):
            validate_event_envelope(envelope)


class TestEventEnvelopeIdempotency:
    """Idempotency: validation is deterministic and repeatable."""

    def test_same_envelope_validates_repeatedly(self):
        envelope = _valid_envelope()
        for _ in range(10):
            validate_event_envelope(envelope)

    def test_envelope_dataclass_is_frozen(self):
        now = datetime.now(timezone.utc)
        uid = uuid6.uuid7()
        env = EventEnvelope(
            event_id=uid,
            event_type="agent.execution_requested.v1",
            event_version=1,
            producer_module="agent",
            routing_key="agent.execution.requested.v1",
            occurred_at=now,
            payload={},
            idempotency_key="key",
            correlation_id=uid,
        )
        with pytest.raises(Exception):
            env.event_type = "modified"  # type: ignore[misc]
