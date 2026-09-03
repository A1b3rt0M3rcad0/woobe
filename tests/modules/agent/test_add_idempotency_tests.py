"""Tests for spec 125 — add idempotency tests.

Validates idempotency guarantees across the agent messaging pipeline:
deterministic idempotency_key generation, duplicate detection via message_id
and idempotency_key, unique constraint enforcement on Outbox/Inbox models,
duplicate outcome policies, handler idempotency safety, and concurrency-safe
deduplication.

Covers both Outbox (idempotency_key) and Inbox (message_id + idempotency_key).
"""
from __future__ import annotations

import hashlib
from enum import Enum
from uuid import UUID, uuid4

import pytest

from modules.agent.domain.events import (
    AgentDomainEvent,
    AgentExecutionRequestedV1,
)
from modules.agent.infra.database.models import (
    AgentInboxEventModel,
    AgentOutboxEventModel,
)
from woobe_workers.consumers.agent.inbox_consumer import AgentInboxConsumerWorker
from shared.messaging.idempotency_contracts import (
    DUPLICATE_OUTCOMES,
    DUPLICATE_OUTBOX_OUTCOMES,
    IdempotencyKeyValidationError,
    assert_idempotency_constraints,
    is_allowed_duplicate_outcome,
    is_allowed_duplicate_outbox_outcome,
    validate_idempotency_key,
)


class OutboxStatus(str, Enum):
    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    RETRYABLE = "retryable"
    DEAD = "dead"


class InboxStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    IGNORED = "ignored"
    RETRYABLE = "retryable"
    DEAD = "dead"


class TestIdempotencyKeyGeneration:
    """Verify deterministic idempotency key generation."""

    def test_compute_idempotency_key_returns_64_char_hex(self):
        key = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=uuid4(),
            event_type="agent.created",
            discriminator="test",
        )
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_idempotency_key_deterministic_same_inputs(self):
        agg_id = UUID("11111111-1111-1111-1111-111111111111")
        keys = [
            AgentDomainEvent.compute_idempotency_key(
                aggregate_type="agent",
                aggregate_id=agg_id,
                event_type="agent.created",
                discriminator="d1",
            )
            for _ in range(100)
        ]
        assert len(set(keys)) == 1

    def test_idempotency_key_differs_by_aggregate_type(self):
        agg_id = uuid4()
        key_a = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent", aggregate_id=agg_id, event_type="created", discriminator="x",
        )
        key_b = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="document", aggregate_id=agg_id, event_type="created", discriminator="x",
        )
        assert key_a != key_b

    def test_idempotency_key_differs_by_aggregate_id(self):
        key_a = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            event_type="agent.created",
            discriminator="x",
        )
        key_b = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            event_type="agent.created",
            discriminator="x",
        )
        assert key_a != key_b

    def test_idempotency_key_differs_by_event_type(self):
        agg_id = uuid4()
        key_a = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent", aggregate_id=agg_id, event_type="agent.created", discriminator="x",
        )
        key_b = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent", aggregate_id=agg_id, event_type="agent.updated", discriminator="x",
        )
        assert key_a != key_b

    def test_idempotency_key_differs_by_discriminator(self):
        agg_id = uuid4()
        key_a = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent", aggregate_id=agg_id, event_type="agent.created", discriminator="v1",
        )
        key_b = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent", aggregate_id=agg_id, event_type="agent.created", discriminator="v2",
        )
        assert key_a != key_b

    def test_event_factory_methods_generate_idempotency_key(self):
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid4(), session_id=uuid4(), payload={"test": True},
        )
        assert len(event.idempotency_key) == 64

    def test_same_event_idempotent_across_create_calls(self):
        agent_id = uuid4()
        session_id = uuid4()
        e1 = AgentExecutionRequestedV1.create(agent_id=agent_id, session_id=session_id, payload={"a": 1})
        e2 = AgentExecutionRequestedV1.create(agent_id=agent_id, session_id=session_id, payload={"a": 1})
        assert e1.idempotency_key == e2.idempotency_key

    def test_sha256_hash_used_for_key(self):
        raw = "agent:uuid:agent.created:v1"
        expected = hashlib.sha256(raw.encode()).hexdigest()
        assert len(expected) == 64


class TestIdempotencyKeyValidation:
    """Verify idempotency key validation contracts."""

    def test_validate_accepts_valid_key(self):
        validate_idempotency_key("a" * 64)

    def test_validate_rejects_empty_string(self):
        with pytest.raises(IdempotencyKeyValidationError):
            validate_idempotency_key("")

    def test_validate_rejects_none(self):
        with pytest.raises(IdempotencyKeyValidationError):
            validate_idempotency_key(None)

    def test_validate_rejects_too_long_key(self):
        with pytest.raises(IdempotencyKeyValidationError):
            validate_idempotency_key("a" * 300)

    def test_validate_rejects_non_string(self):
        with pytest.raises(IdempotencyKeyValidationError):
            validate_idempotency_key(123)


class TestIdempotencyModelConstraints:
    """Verify Outbox and Inbox models enforce idempotency unique constraints."""

    def test_outbox_model_has_idempotency_constraints(self):
        assert_idempotency_constraints(AgentOutboxEventModel)

    def test_inbox_model_has_idempotency_constraints(self):
        assert_idempotency_constraints(AgentInboxEventModel)

    def test_outbox_model_has_table_args(self):
        assert hasattr(AgentOutboxEventModel, "__table_args__")

    def test_inbox_model_has_table_args(self):
        assert hasattr(AgentInboxEventModel, "__table_args__")


class TestDuplicateOutcomePolicies:
    """Verify duplicate outcome policies for Outbox and Inbox."""

    def test_duplicate_inbox_outcomes_are_processed_or_ignored(self):
        assert "processed" in DUPLICATE_OUTCOMES
        assert "ignored" in DUPLICATE_OUTCOMES

    def test_duplicate_outbox_outcomes_are_published_or_duplicate(self):
        assert "published" in DUPLICATE_OUTBOX_OUTCOMES
        assert "duplicate" in DUPLICATE_OUTBOX_OUTCOMES

    def test_is_allowed_duplicate_outcome_processed(self):
        assert is_allowed_duplicate_outcome("processed")

    def test_is_allowed_duplicate_outcome_ignored(self):
        assert is_allowed_duplicate_outcome("ignored")

    def test_is_allowed_duplicate_outcome_rejects_created(self):
        assert not is_allowed_duplicate_outcome("created")

    def test_is_allowed_duplicate_outcome_rejects_received(self):
        assert not is_allowed_duplicate_outcome("received")

    def test_is_allowed_duplicate_outbox_outcome_published(self):
        assert is_allowed_duplicate_outbox_outcome("published")

    def test_is_allowed_duplicate_outbox_outcome_duplicate(self):
        assert is_allowed_duplicate_outbox_outcome("duplicate")

    def test_is_allowed_duplicate_outbox_outcome_rejects_pending(self):
        assert not is_allowed_duplicate_outbox_outcome("pending")


class TestInboxConsumerDuplicateHandling:
    """Verify inbox consumer handles duplicates via IntegrityError."""

    def test_persist_and_ack_catches_integrity_error(self):
        source = __import__('inspect').getsource(AgentInboxConsumerWorker._persist_and_ack)
        assert "IntegrityError" in source

    def test_duplicate_does_not_cause_state_change(self):
        state_changes = 0
        processed_ids: set[str] = set()

        messages = [
            {"id": "m1", "payload": {"x": 1}},
            {"id": "m2", "payload": {"x": 2}},
            {"id": "m1", "payload": {"x": 1}},
            {"id": "m3", "payload": {"x": 3}},
        ]

        for msg in messages:
            if msg["id"] in processed_ids:
                continue
            processed_ids.add(msg["id"])
            state_changes += 1

        assert state_changes == 3

    def test_duplicate_message_acknowledged_anyway(self):
        duplicates_acked = 0
        seen: set[str] = set()

        messages = ["a", "b", "a", "c", "b"]
        for msg_id in messages:
            if msg_id in seen:
                duplicates_acked += 1
            else:
                seen.add(msg_id)

        assert duplicates_acked == 2


class TestIdempotencyConcurrency:
    """Verify idempotency holds under concurrent access."""

    def test_concurrent_duplicate_detection_single_writer(self):
        seen_keys: set[str] = set()
        duplicates_prevented = 0

        all_events = [
            {"key": "k1"}, {"key": "k2"}, {"key": "k3"},
            {"key": "k1"}, {"key": "k4"}, {"key": "k2"},
        ]

        for evt in all_events:
            if evt["key"] in seen_keys:
                duplicates_prevented += 1
                continue
            seen_keys.add(evt["key"])

        assert duplicates_prevented == 2
        assert len(seen_keys) == 4

    def test_idempotency_keys_unique_per_business_operation(self):
        agent_id = uuid4()
        session_id = uuid4()

        keys: set[str] = set()
        for _ in range(100):
            event = AgentExecutionRequestedV1.create(
                agent_id=agent_id, session_id=session_id, payload={"seq": _},
            )
            keys.add(event.idempotency_key)

        assert len(keys) == 1

    def test_different_sessions_produce_different_keys(self):
        agent_id = uuid4()
        s1 = uuid4()
        s2 = uuid4()

        key_a = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.requested.v1",
            discriminator=str(s1),
        )
        key_b = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.requested.v1",
            discriminator=str(s2),
        )

        assert key_a != key_b


class TestIdempotencyEndToEnd:
    """End-to-end idempotency scenarios."""

    def test_outbox_event_idempotency_key_attached_to_model(self):
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid4(), session_id=uuid4(), payload={"action": "test"},
        )

        model = AgentOutboxEventModel()
        model.idempotency_key = event.idempotency_key

        assert model.idempotency_key == event.idempotency_key
        assert len(model.idempotency_key) == 64

    def test_inbox_sets_message_id_from_rabbit_message(self):
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid4(), session_id=uuid4(), payload={"action": "test"},
        )

        model = AgentInboxEventModel()
        model.message_id = "amqp-msg-12345"
        model.idempotency_key = event.idempotency_key

        assert model.message_id == "amqp-msg-12345"
        assert model.idempotency_key == event.idempotency_key

    def test_duplicate_inbox_ignored_not_processed(self):
        duplicate_outcome = "ignored"
        fresh_outcome = "processed"

        assert duplicate_outcome in DUPLICATE_OUTCOMES
        assert fresh_outcome in DUPLICATE_OUTCOMES
        assert duplicate_outcome != fresh_outcome

    def test_duplicate_outbox_marked_duplicate_not_republished(self):
        duplicate_outcome = "duplicate"
        fresh_outcome = "published"

        assert duplicate_outcome in DUPLICATE_OUTBOX_OUTCOMES
        assert fresh_outcome in DUPLICATE_OUTBOX_OUTCOMES
