"""Tests for spec 078 — create agent inbox status transition policy."""
import inspect

import pytest

from modules.agent.infra.database.models import AgentInboxEventModel
from modules.agent.infra.database.repositories import (
    AGENT_INBOX_VALID_TRANSITIONS,
    SQLAlchemyAgentInboxRepository,
)


class TestInboxStatusTransitionPolicyContract:
    """Verify the inbox status transition policy matches spec 078 contract."""

    def test_allowed_states(self):
        expected_states = {"received", "processing", "processed", "retryable", "dead", "ignored"}
        defined_sources = set(AGENT_INBOX_VALID_TRANSITIONS.keys())
        defined_targets = set()
        for targets in AGENT_INBOX_VALID_TRANSITIONS.values():
            defined_targets.update(targets)
        all_states = defined_sources | defined_targets
        assert all_states == expected_states

    def test_received_transitions_to_processing_and_ignored(self):
        allowed = AGENT_INBOX_VALID_TRANSITIONS["received"]
        assert allowed == {"processing", "ignored"}

    def test_processing_transitions_to_processed_retryable_dead(self):
        allowed = AGENT_INBOX_VALID_TRANSITIONS["processing"]
        assert allowed == {"processed", "retryable", "dead"}

    def test_retryable_only_transitions_to_processing(self):
        allowed = AGENT_INBOX_VALID_TRANSITIONS["retryable"]
        assert allowed == {"processing"}

    def test_processed_is_terminal(self):
        assert "processed" not in AGENT_INBOX_VALID_TRANSITIONS

    def test_dead_is_terminal(self):
        assert "dead" not in AGENT_INBOX_VALID_TRANSITIONS

    def test_ignored_is_terminal(self):
        assert "ignored" not in AGENT_INBOX_VALID_TRANSITIONS


class TestInboxValidTransitions:
    """Verify all valid transitions are accepted by _validate_transition."""

    @pytest.mark.parametrize(
        "current,target",
        [
            ("received", "processing"),
            ("received", "ignored"),
            ("processing", "processed"),
            ("processing", "retryable"),
            ("processing", "dead"),
            ("retryable", "processing"),
        ],
    )
    def test_valid_transition_accepted(self, current: str, target: str):
        SQLAlchemyAgentInboxRepository._validate_transition(current, target)


class TestInboxInvalidTransitions:
    """Verify all invalid transitions are rejected."""

    @pytest.mark.parametrize(
        "current,target",
        [
            ("received", "processed"),
            ("received", "retryable"),
            ("received", "dead"),
            ("received", "received"),
            ("processing", "received"),
            ("processing", "processing"),
            ("processing", "ignored"),
            ("retryable", "received"),
            ("retryable", "processed"),
            ("retryable", "retryable"),
            ("retryable", "dead"),
            ("retryable", "ignored"),
            ("processed", "received"),
            ("processed", "processing"),
            ("processed", "processed"),
            ("processed", "retryable"),
            ("processed", "dead"),
            ("processed", "ignored"),
            ("dead", "received"),
            ("dead", "processing"),
            ("dead", "processed"),
            ("dead", "retryable"),
            ("dead", "dead"),
            ("dead", "ignored"),
            ("ignored", "received"),
            ("ignored", "processing"),
            ("ignored", "processed"),
            ("ignored", "retryable"),
            ("ignored", "dead"),
            ("ignored", "ignored"),
        ],
    )
    def test_invalid_transition_rejected(self, current: str, target: str):
        with pytest.raises(ValueError, match="Invalid inbox status transition"):
            SQLAlchemyAgentInboxRepository._validate_transition(current, target)


class TestInboxIdempotency:
    """Verify idempotency constraints are defined on the inbox model."""

    def test_unique_message_id_constraint_exists(self):
        from sqlalchemy import UniqueConstraint as UC

        table = AgentInboxEventModel.__table__
        uq_constraints = [
            c
            for c in table.constraints
            if isinstance(c, UC)
            and "message_id" in {col.name for col in c.columns}
        ]
        assert len(uq_constraints) == 1
        assert uq_constraints[0].name == "uq_agent_inbox_message_id"

    def test_unique_idempotency_key_constraint_exists(self):
        from sqlalchemy import UniqueConstraint as UC

        table = AgentInboxEventModel.__table__
        uq_constraints = [
            c
            for c in table.constraints
            if isinstance(c, UC)
            and "idempotency_key" in {col.name for col in c.columns}
        ]
        assert len(uq_constraints) == 1
        assert uq_constraints[0].name == "uq_agent_inbox_idempotency_key"

    def test_message_id_not_nullable(self):
        col = AgentInboxEventModel.__table__.columns["message_id"]
        assert not col.nullable

    def test_idempotency_key_not_nullable(self):
        col = AgentInboxEventModel.__table__.columns["idempotency_key"]
        assert not col.nullable


class TestInboxConcurrency:
    """Verify claim_batch uses FOR UPDATE SKIP LOCKED and sets processing status."""

    def test_claim_batch_uses_skip_locked(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "skip_locked" in source

    def test_claim_batch_sets_processing_status(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert '"processing"' in source or "'processing'" in source

    def test_claim_batch_sets_locked_by(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "locked_by" in source
        assert "locked_at" in source

    def test_claim_batch_filters_received_and_retryable(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "received" in source
        assert "retryable" in source

    def test_claim_batch_checks_available_at(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "available_at" in source

    def test_two_tasks_cannot_claim_same_record(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "with_for_update" in source
        assert "skip_locked=True" in source


class TestInboxMarkIgnored:
    """Verify mark_ignored method exists and follows transition policy."""

    def test_repository_has_mark_ignored(self):
        assert hasattr(SQLAlchemyAgentInboxRepository, "mark_ignored")

    def test_mark_ignored_validates_transition(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.mark_ignored)
        assert "_validate_transition" in source
        assert '"ignored"' in source or "'ignored'" in source
