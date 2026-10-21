"""Tests for spec 070 — create agent outbox model and repository."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.dialects import postgresql

from modules.agent.domain.events import AgentExecutionRequestedV1
from modules.agent.infra.database.models import AgentOutboxEventModel
from modules.agent.infra.messaging.event_mappers import domain_event_to_outbox
from modules.agent.infra.database.repositories import (
    AGENT_OUTBOX_VALID_TRANSITIONS,
    SQLAlchemyAgentOutboxRepository,
)


class TestAgentOutboxModelStructure:
    """Verify model has correct columns, constraints, and indices."""

    def test_table_name_and_schema(self):
        assert AgentOutboxEventModel.__tablename__ == "agent_outbox_events"
        table_args = AgentOutboxEventModel.__table_args__
        schema = None
        for arg in table_args:
            if isinstance(arg, dict):
                schema = arg.get("schema")
        assert schema == "agent"

    def test_required_columns_exist(self):
        columns = AgentOutboxEventModel.__table__.columns
        required = [
            "id", "aggregate_type", "aggregate_id", "event_type",
            "event_version", "routing_key", "payload", "metadata",
            "idempotency_key", "correlation_id", "causation_id",
            "status", "attempts", "available_at", "locked_at",
            "locked_by", "published_at", "error", "created_at", "updated_at",
        ]
        column_names = {c.name for c in columns}
        for col_name in required:
            assert col_name in column_names, f"Missing column: {col_name}"

    def test_idempotency_key_unique_constraint(self):
        table = AgentOutboxEventModel.__table__
        unique_constraints = [
            c for c in table.constraints
            if hasattr(c, "columns") and "idempotency_key" in {col.name for col in c.columns}
        ]
        assert len(unique_constraints) >= 1, (
            "Missing UNIQUE constraint on idempotency_key"
        )

    def test_partial_index_for_pending(self):
        table = AgentOutboxEventModel.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_agent_outbox_pending" in index_names

    def test_correlation_id_index(self):
        table = AgentOutboxEventModel.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_agent_outbox_correlation_id" in index_names

    def test_aggregate_index(self):
        table = AgentOutboxEventModel.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_agent_outbox_aggregate" in index_names

    def test_correlation_id_not_nullable(self):
        col = AgentOutboxEventModel.__table__.columns["correlation_id"]
        assert not col.nullable


class TestAgentOutboxStatusTransitions:
    """Verify status transitions follow expected policy (updated by spec 077)."""

    def test_valid_transitions_from_pending(self):
        allowed = AGENT_OUTBOX_VALID_TRANSITIONS["pending"]
        assert "publishing" in allowed
        assert len(allowed) == 1

    def test_valid_transitions_from_publishing(self):
        allowed = AGENT_OUTBOX_VALID_TRANSITIONS["publishing"]
        assert "published" in allowed
        assert "retryable" in allowed
        assert "dead" in allowed

    def test_valid_transitions_from_retryable(self):
        allowed = AGENT_OUTBOX_VALID_TRANSITIONS["retryable"]
        assert "publishing" in allowed
        assert len(allowed) == 1

    def test_invalid_transition_from_published(self):
        assert "published" not in AGENT_OUTBOX_VALID_TRANSITIONS

    def test_invalid_transition_from_dead(self):
        assert "dead" not in AGENT_OUTBOX_VALID_TRANSITIONS

    def test_validate_transition_rejects_invalid(self):
        with pytest.raises(ValueError, match="Invalid outbox status transition"):
            SQLAlchemyAgentOutboxRepository._validate_transition("published", "pending")

    def test_validate_transition_accepts_valid(self):
        SQLAlchemyAgentOutboxRepository._validate_transition("pending", "publishing")
        SQLAlchemyAgentOutboxRepository._validate_transition("publishing", "published")
        SQLAlchemyAgentOutboxRepository._validate_transition("publishing", "retryable")
        SQLAlchemyAgentOutboxRepository._validate_transition("retryable", "publishing")


class TestAgentOutboxRepositoryInterface:
    """Verify repository has required methods."""

    def test_repository_has_add(self):
        assert hasattr(SQLAlchemyAgentOutboxRepository, "add")

    def test_repository_has_claim_batch(self):
        assert hasattr(SQLAlchemyAgentOutboxRepository, "claim_batch")

    def test_repository_has_mark_published(self):
        assert hasattr(SQLAlchemyAgentOutboxRepository, "mark_published")

    def test_repository_has_mark_retryable(self):
        assert hasattr(SQLAlchemyAgentOutboxRepository, "mark_retryable")

    def test_repository_has_mark_dead(self):
        assert hasattr(SQLAlchemyAgentOutboxRepository, "mark_dead")


class TestAgentOutboxIdempotency:
    """Verify idempotency key constraint prevents duplicates."""

    def test_unique_constraint_on_idempotency_key_exists(self):
        table = AgentOutboxEventModel.__table__
        from sqlalchemy import UniqueConstraint as UC
        uq_constraints = [
            c for c in table.constraints
            if isinstance(c, UC) and "idempotency_key" in {col.name for col in c.columns}
        ]
        assert len(uq_constraints) == 1
        assert uq_constraints[0].name == "uq_agent_outbox_idempotency_key"


class TestAgentOutboxConcurrency:
    """Verify claim_batch uses FOR UPDATE SKIP LOCKED for concurrency safety."""

    def test_claim_batch_uses_skip_locked(self):
        import inspect
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "skip_locked" in source, (
            "claim_batch must use FOR UPDATE SKIP LOCKED for concurrency safety"
        )

    def test_claim_batch_sets_locked_by(self):
        import inspect
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "locked_by" in source
        assert "locked_at" in source

    @pytest.mark.asyncio
    async def test_claim_batch_recovers_stale_publishing_events_atomically(self):
        event = domain_event_to_outbox(AgentExecutionRequestedV1.create(
            agent_id="00000000-0000-0000-0000-000000000001",
            session_id="00000000-0000-0000-0000-000000000002",
            payload={"action": "recover"},
        ))
        event.status = "publishing"
        event.locked_at = datetime.now(timezone.utc) - timedelta(seconds=301)
        event.locked_by = "abandoned-worker"

        class Result:
            def scalars(self):
                return self

            def all(self):
                return [event]

        class Session:
            statement = None

            async def execute(self, statement):
                self.statement = statement
                return Result()

            async def flush(self):
                return None

        session = Session()
        events = await SQLAlchemyAgentOutboxRepository(session).claim_batch(
            batch_size=10,
            locked_by="recovery-worker",
        )

        sql = str(session.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        ))
        assert "IN ('pending', 'retryable', 'publishing')" in sql
        assert "locked_at IS NULL" in sql
        assert "INTERVAL '300 seconds'" in sql
        assert "FOR UPDATE SKIP LOCKED" in sql
        assert events == [event]
        assert event.status == "publishing"
        assert event.locked_by == "recovery-worker"
        assert event.locked_at > datetime.now(timezone.utc) - timedelta(seconds=1)
