"""Tests for spec 103 — standardize event idempotency."""
from __future__ import annotations

import pytest

from shared.messaging.idempotency_contracts import (
    IDEMPOTENCY_KEY_MAX_LENGTH,
    DUPLICATE_OUTCOMES,
    DUPLICATE_OUTBOX_OUTCOMES,
    IdempotencyKeyValidationError,
    assert_idempotency_constraints,
    is_allowed_duplicate_outcome,
    is_allowed_duplicate_outbox_outcome,
    validate_idempotency_key,
)


class TestIdempotencyKeyValidation:
    """Success: valid idempotency keys accepted."""

    def test_valid_key_accepted(self):
        validate_idempotency_key("abc123-hash-key")
        validate_idempotency_key("a" * IDEMPOTENCY_KEY_MAX_LENGTH)

    def test_at_max_length_accepted(self):
        validate_idempotency_key("x" * IDEMPOTENCY_KEY_MAX_LENGTH)


class TestIdempotencyKeyRejectsInvalid:
    """Failure: empty, too long, or type-invalid keys rejected."""

    def test_empty_string_rejected(self):
        with pytest.raises(IdempotencyKeyValidationError):
            validate_idempotency_key("")

    def test_too_long_rejected(self):
        long_key = "x" * (IDEMPOTENCY_KEY_MAX_LENGTH + 1)
        with pytest.raises(IdempotencyKeyValidationError):
            validate_idempotency_key(long_key)


class TestIdempotencyDuplicateOutcomes:
    """Duplicate delivery must not cause second state change."""

    def test_duplicate_inbox_outcomes_are_idempotent(self):
        assert "processed" in DUPLICATE_OUTCOMES
        assert "ignored" in DUPLICATE_OUTCOMES

    def test_duplicate_outbox_outcomes_are_idempotent(self):
        assert "published" in DUPLICATE_OUTBOX_OUTCOMES
        assert "duplicate" in DUPLICATE_OUTBOX_OUTCOMES

    def test_is_allowed_duplicate_outcome_accepts_valid(self):
        for status in ("processed", "ignored"):
            assert is_allowed_duplicate_outcome(status)
        assert not is_allowed_duplicate_outcome("pending")
        assert not is_allowed_duplicate_outcome("completed")

    def test_is_allowed_duplicate_outbox_outcome_accepts_valid(self):
        for status in ("published", "duplicate"):
            assert is_allowed_duplicate_outbox_outcome(status)
        assert not is_allowed_duplicate_outbox_outcome("pending")
        assert not is_allowed_duplicate_outbox_outcome("attempted")


class TestAgentModelIdempotencyConstraints:
    """Agent outbox/inbox models have unique constraints for deduplication."""

    def test_agent_outbox_has_idempotency_constraints(self):
        from modules.agent.infra.database.models import AgentOutboxEventModel

        assert_idempotency_constraints(AgentOutboxEventModel)

    def test_agent_inbox_has_idempotency_constraints(self):
        from modules.agent.infra.database.models import AgentInboxEventModel

        assert_idempotency_constraints(AgentInboxEventModel)


class TestIdempotencyKeyDeterminism:
    """Same inputs must produce same idempotency_key."""

    def test_agent_domain_event_idempotency_key_deterministic(self):
        from modules.agent.domain.events import AgentDomainEvent
        import uuid6

        agent_id = uuid6.uuid7()
        key1 = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.requested.v1",
            discriminator="test-001",
        )
        key2 = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.requested.v1",
            discriminator="test-001",
        )
        assert key1 == key2
        validate_idempotency_key(key1)

    def test_different_discriminator_produces_different_key(self):
        from modules.agent.domain.events import AgentDomainEvent
        import uuid6

        agent_id = uuid6.uuid7()
        key1 = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.requested.v1",
            discriminator="a",
        )
        key2 = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.requested.v1",
            discriminator="b",
        )
        assert key1 != key2

    def test_different_aggregate_id_produces_different_key(self):
        from modules.agent.domain.events import AgentDomainEvent
        import uuid6

        key1 = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=uuid6.uuid7(),
            event_type="agent.execution.requested.v1",
            discriminator="test",
        )
        key2 = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=uuid6.uuid7(),
            event_type="agent.execution.requested.v1",
            discriminator="test",
        )
        assert key1 != key2
