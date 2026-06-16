"""Tests for spec 071 — create agent inbox model and repository."""
import pytest

from modules.agent.infra.database.models import AgentInboxEventModel
from modules.agent.infra.database.repositories import (
    AGENT_INBOX_VALID_TRANSITIONS,
    SQLAlchemyAgentInboxRepository,
)


class TestAgentInboxModelStructure:
    """Verify model has correct columns, constraints, and indices."""

    def test_table_name_and_schema(self):
        assert AgentInboxEventModel.__tablename__ == "agent_inbox_events"
        table_args = AgentInboxEventModel.__table_args__
        schema = None
        for arg in table_args:
            if isinstance(arg, dict):
                schema = arg.get("schema")
        assert schema == "agent"

    def test_required_columns_exist(self):
        columns = AgentInboxEventModel.__table__.columns
        required = [
            "id", "message_id", "producer_module", "consumer_module",
            "event_type", "event_version", "routing_key", "payload",
            "headers", "idempotency_key", "correlation_id", "causation_id",
            "status", "attempts", "available_at", "locked_at",
            "locked_by", "processed_at", "error", "created_at", "updated_at",
        ]
        column_names = {c.name for c in columns}
        for col_name in required:
            assert col_name in column_names, f"Missing column: {col_name}"

    def test_message_id_unique_constraint(self):
        table = AgentInboxEventModel.__table__
        from sqlalchemy import UniqueConstraint as UC
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "message_id" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1
        assert uq[0].name == "uq_agent_inbox_message_id"

    def test_idempotency_key_unique_constraint(self):
        table = AgentInboxEventModel.__table__
        from sqlalchemy import UniqueConstraint as UC
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "idempotency_key" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1
        assert uq[0].name == "uq_agent_inbox_idempotency_key"

    def test_partial_index_for_pending(self):
        table = AgentInboxEventModel.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_agent_inbox_pending" in index_names

    def test_correlation_id_index(self):
        table = AgentInboxEventModel.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_agent_inbox_correlation_id" in index_names

    def test_correlation_id_not_nullable(self):
        col = AgentInboxEventModel.__table__.columns["correlation_id"]
        assert not col.nullable


class TestAgentInboxStatusTransitions:
    """Verify status transitions follow expected policy."""

    def test_valid_transitions_from_received(self):
        allowed = AGENT_INBOX_VALID_TRANSITIONS["received"]
        assert "processing" in allowed

    def test_valid_transitions_from_processing(self):
        allowed = AGENT_INBOX_VALID_TRANSITIONS["processing"]
        assert "processed" in allowed
        assert "retryable" in allowed
        assert "dead" in allowed

    def test_valid_transitions_from_retryable(self):
        allowed = AGENT_INBOX_VALID_TRANSITIONS["retryable"]
        assert "processing" in allowed

    def test_no_transitions_from_processed(self):
        assert "processed" not in AGENT_INBOX_VALID_TRANSITIONS

    def test_no_transitions_from_dead(self):
        assert "dead" not in AGENT_INBOX_VALID_TRANSITIONS

    def test_validate_transition_rejects_invalid(self):
        with pytest.raises(ValueError, match="Invalid inbox status transition"):
            SQLAlchemyAgentInboxRepository._validate_transition("processed", "received")

    def test_validate_transition_accepts_valid(self):
        SQLAlchemyAgentInboxRepository._validate_transition("received", "processing")
        SQLAlchemyAgentInboxRepository._validate_transition("processing", "processed")
        SQLAlchemyAgentInboxRepository._validate_transition("processing", "retryable")
        SQLAlchemyAgentInboxRepository._validate_transition("retryable", "processing")


class TestAgentInboxRepositoryInterface:
    """Verify repository has required methods."""

    def test_repository_has_save_received(self):
        assert hasattr(SQLAlchemyAgentInboxRepository, "save_received")

    def test_repository_has_claim_batch(self):
        assert hasattr(SQLAlchemyAgentInboxRepository, "claim_batch")

    def test_repository_has_mark_processing(self):
        assert hasattr(SQLAlchemyAgentInboxRepository, "mark_processing")

    def test_repository_has_mark_processed(self):
        assert hasattr(SQLAlchemyAgentInboxRepository, "mark_processed")

    def test_repository_has_mark_retryable(self):
        assert hasattr(SQLAlchemyAgentInboxRepository, "mark_retryable")

    def test_repository_has_mark_dead(self):
        assert hasattr(SQLAlchemyAgentInboxRepository, "mark_dead")


class TestAgentInboxIdempotency:
    """Verify idempotency constraints prevent duplicates."""

    def test_unique_constraint_on_message_id(self):
        table = AgentInboxEventModel.__table__
        from sqlalchemy import UniqueConstraint as UC
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "message_id" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1

    def test_unique_constraint_on_idempotency_key(self):
        table = AgentInboxEventModel.__table__
        from sqlalchemy import UniqueConstraint as UC
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "idempotency_key" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1


class TestAgentInboxConcurrency:
    """Verify claim_batch uses FOR UPDATE SKIP LOCKED for concurrency safety."""

    def test_claim_batch_uses_skip_locked(self):
        import inspect
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "skip_locked" in source

    def test_claim_batch_sets_locked_by(self):
        import inspect
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "locked_by" in source
        assert "locked_at" in source
