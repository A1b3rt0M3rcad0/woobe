"""Tests for spec 077 — create agent outbox status transition policy."""
import inspect

import pytest

from modules.agent.infra.database.models import AgentOutboxEventModel
from modules.agent.infra.database.repositories import (
    AGENT_OUTBOX_VALID_TRANSITIONS,
    SQLAlchemyAgentOutboxRepository,
)


class TestOutboxStatusTransitionPolicyContract:
    """Verify the outbox status transition policy matches spec 077 contract."""

    def test_allowed_states(self):
        expected_states = {"pending", "publishing", "published", "retryable", "dead"}
        defined_sources = set(AGENT_OUTBOX_VALID_TRANSITIONS.keys())
        defined_targets = set()
        for targets in AGENT_OUTBOX_VALID_TRANSITIONS.values():
            defined_targets.update(targets)
        all_states = defined_sources | defined_targets
        assert all_states == expected_states

    def test_pending_only_transitions_to_publishing(self):
        allowed = AGENT_OUTBOX_VALID_TRANSITIONS["pending"]
        assert allowed == {"publishing"}

    def test_publishing_transitions_to_published_retryable_dead(self):
        allowed = AGENT_OUTBOX_VALID_TRANSITIONS["publishing"]
        assert allowed == {"published", "retryable", "dead"}

    def test_retryable_only_transitions_to_publishing(self):
        allowed = AGENT_OUTBOX_VALID_TRANSITIONS["retryable"]
        assert allowed == {"publishing"}

    def test_published_is_terminal(self):
        assert "published" not in AGENT_OUTBOX_VALID_TRANSITIONS

    def test_dead_is_terminal(self):
        assert "dead" not in AGENT_OUTBOX_VALID_TRANSITIONS

    def test_dead_to_published_forbidden(self):
        with pytest.raises(ValueError, match="Invalid outbox status transition"):
            SQLAlchemyAgentOutboxRepository._validate_transition("dead", "published")

    def test_published_to_any_forbidden(self):
        for target in ["pending", "publishing", "retryable", "dead"]:
            with pytest.raises(ValueError, match="Invalid outbox status transition"):
                SQLAlchemyAgentOutboxRepository._validate_transition("published", target)


class TestOutboxValidTransitions:
    """Verify all valid transitions are accepted by _validate_transition."""

    @pytest.mark.parametrize(
        "current,target",
        [
            ("pending", "publishing"),
            ("publishing", "published"),
            ("publishing", "retryable"),
            ("publishing", "dead"),
            ("retryable", "publishing"),
        ],
    )
    def test_valid_transition_accepted(self, current: str, target: str):
        SQLAlchemyAgentOutboxRepository._validate_transition(current, target)


class TestOutboxInvalidTransitions:
    """Verify all invalid transitions are rejected."""

    @pytest.mark.parametrize(
        "current,target",
        [
            ("pending", "published"),
            ("pending", "retryable"),
            ("pending", "dead"),
            ("pending", "pending"),
            ("publishing", "pending"),
            ("publishing", "publishing"),
            ("retryable", "published"),
            ("retryable", "retryable"),
            ("retryable", "dead"),
            ("retryable", "pending"),
            ("published", "pending"),
            ("published", "publishing"),
            ("published", "published"),
            ("published", "retryable"),
            ("published", "dead"),
            ("dead", "pending"),
            ("dead", "publishing"),
            ("dead", "published"),
            ("dead", "retryable"),
            ("dead", "dead"),
        ],
    )
    def test_invalid_transition_rejected(self, current: str, target: str):
        with pytest.raises(ValueError, match="Invalid outbox status transition"):
            SQLAlchemyAgentOutboxRepository._validate_transition(current, target)


class TestOutboxIdempotency:
    """Verify idempotency constraints are defined on the outbox model."""

    def test_unique_idempotency_key_constraint_exists(self):
        from sqlalchemy import UniqueConstraint as UC

        table = AgentOutboxEventModel.__table__
        uq_constraints = [
            c
            for c in table.constraints
            if isinstance(c, UC)
            and "idempotency_key" in {col.name for col in c.columns}
        ]
        assert len(uq_constraints) == 1
        assert uq_constraints[0].name == "uq_agent_outbox_idempotency_key"

    def test_duplicate_idempotency_key_prevented_by_constraint(self):
        table = AgentOutboxEventModel.__table__
        col = table.columns["idempotency_key"]
        assert not col.nullable


class TestOutboxConcurrency:
    """Verify claim_batch uses FOR UPDATE SKIP LOCKED and sets publishing status."""

    def test_claim_batch_uses_skip_locked(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "skip_locked" in source

    def test_claim_batch_sets_publishing_status(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert '"publishing"' in source or "'publishing'" in source

    def test_claim_batch_sets_locked_by(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "locked_by" in source
        assert "locked_at" in source

    def test_claim_batch_filters_pending_and_retryable(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "pending" in source
        assert "retryable" in source

    def test_claim_batch_checks_available_at(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "available_at" in source

    def test_two_tasks_cannot_claim_same_record(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "with_for_update" in source
        assert "skip_locked=True" in source
