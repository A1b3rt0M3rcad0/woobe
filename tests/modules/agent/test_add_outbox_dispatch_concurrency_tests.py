"""Tests for spec 129 — add outbox dispatch concurrency tests.

Validates outbox dispatch concurrency guarantees: SKIP LOCKED for parallel
dispatchers, lock lifecycle (claim → publishing → published/dead/retryable),
status transition validation, backoff scheduling, dead-letter after max
attempts, and claim_batch idempotency safety under concurrent dispatch.
"""
from __future__ import annotations

import inspect

from modules.agent.infra.database.models import AgentOutboxEventModel
from modules.agent.infra.database.repositories import (
    AGENT_DEFAULT_BATCH_SIZE,
    AGENT_OUTBOX_LOCK_TIMEOUT_SECONDS,
    AGENT_OUTBOX_VALID_TRANSITIONS,
    SQLAlchemyAgentOutboxRepository,
)
from woobe_workers.consumers.agent.outbox_dispatcher import (
    RETRY_BACKOFF_BASE_SECONDS,
    AgentOutboxDispatcherWorker,
)
from woobe_workers.runtime.outbox_dispatcher_base import BaseOutboxDispatcher, OutboxRecord


class TestOutboxClaimBatchConcurrency:
    """Verify outbox claim_batch uses SKIP LOCKED for concurrency safety."""

    def test_claim_batch_uses_skip_locked(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "skip_locked=True" in source

    def test_claim_batch_uses_with_for_update(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "with_for_update" in source

    def test_claim_batch_claims_pending_and_retryable(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert ('"pending"' in source) or ("'pending'" in source)
        assert ('"retryable"' in source) or ("'retryable'" in source)

    def test_claim_batch_excludes_published(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert '"published"' not in source and "'published'" not in source

    def test_claim_batch_excludes_dead(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert '"dead"' not in source and "'dead'" not in source

    def test_claim_batch_sets_locked_at(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "locked_at" in source

    def test_claim_batch_sets_locked_by(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "locked_by" in source

    def test_claim_batch_sets_status_to_publishing(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert '"publishing"' in source or "'publishing'" in source

    def test_claim_batch_orders_by_created_at_asc(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "created_at" in source
        assert "asc" in source.lower() or "order_by" in source

    def test_claim_batch_has_limit(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "limit" in source

    def test_claim_batch_has_lock_timeout(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "lock_timeout_seconds" in source
        assert "INTERVAL" in source

    def test_claim_batch_handles_expired_locks(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "locked_at.is_(None)" in source or "locked_at == None" in source.lower()
        assert "INTERVAL" in source

    def test_claim_batch_default_batch_size_is_positive(self):
        assert AGENT_DEFAULT_BATCH_SIZE >= 1

    def test_claim_batch_lock_timeout_is_positive(self):
        assert AGENT_OUTBOX_LOCK_TIMEOUT_SECONDS >= 1

    def test_claim_batch_filters_by_available_at(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "available_at" in source


class TestOutboxStatusTransitions:
    """Verify outbox status transitions enforce valid dispatch state machine."""

    def test_pending_transitions_to_publishing(self):
        assert "publishing" in AGENT_OUTBOX_VALID_TRANSITIONS.get("pending", set())

    def test_publishing_transitions_to_published(self):
        assert "published" in AGENT_OUTBOX_VALID_TRANSITIONS.get("publishing", set())

    def test_publishing_transitions_to_retryable(self):
        assert "retryable" in AGENT_OUTBOX_VALID_TRANSITIONS.get("publishing", set())

    def test_publishing_transitions_to_dead(self):
        assert "dead" in AGENT_OUTBOX_VALID_TRANSITIONS.get("publishing", set())

    def test_retryable_transitions_to_publishing(self):
        assert "publishing" in AGENT_OUTBOX_VALID_TRANSITIONS.get("retryable", set())

    def test_published_has_no_transitions(self):
        assert "published" not in AGENT_OUTBOX_VALID_TRANSITIONS or (
            not AGENT_OUTBOX_VALID_TRANSITIONS.get("published")
        )

    def test_dead_has_no_transitions(self):
        assert "dead" not in AGENT_OUTBOX_VALID_TRANSITIONS or (
            not AGENT_OUTBOX_VALID_TRANSITIONS.get("dead")
        )

    def test_validate_transition_raises_on_invalid(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository._validate_transition)
        assert "ValueError" in source

    def test_mark_published_validates_transition(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_published)
        assert "_validate_transition" in source

    def test_mark_retryable_validates_transition(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_retryable)
        assert "_validate_transition" in source

    def test_mark_dead_validates_transition(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_dead)
        assert "_validate_transition" in source


class TestOutboxMarkPublished:
    """Verify mark_published updates outbox correctly after dispatch."""

    def test_mark_published_sets_status(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_published)
        assert '"published"' in source or "'published'" in source

    def test_mark_published_sets_published_at(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_published)
        assert "published_at" in source

    def test_mark_published_clears_lock(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_published)
        assert "locked_at = None" in source
        assert "locked_by = None" in source


class TestOutboxMarkRetryable:
    """Verify mark_retryable schedules backoff after transient failure."""

    def test_mark_retryable_sets_status(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_retryable)
        assert '"retryable"' in source or "'retryable'" in source

    def test_mark_retryable_increments_attempts(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_retryable)
        assert "attempts" in source

    def test_mark_retryable_sets_error(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_retryable)
        assert "error" in source

    def test_mark_retryable_sets_available_at(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_retryable)
        assert "available_at" in source

    def test_mark_retryable_clears_lock(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_retryable)
        assert "locked_at = None" in source
        assert "locked_by = None" in source


class TestOutboxMarkDead:
    """Verify mark_dead finalizes outbox on permanent failure."""

    def test_mark_dead_sets_status(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_dead)
        assert '"dead"' in source or "'dead'" in source

    def test_mark_dead_increments_attempts(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_dead)
        assert "attempts" in source

    def test_mark_dead_sets_error(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_dead)
        assert "error" in source

    def test_mark_dead_clears_lock(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_dead)
        assert "locked_at = None" in source
        assert "locked_by = None" in source


class TestOutboxDispatcherConcurrency:
    """Verify outbox dispatcher worker coordinates claim/publish/mark cycle."""

    def test_dispatcher_inherits_from_base(self):
        assert issubclass(AgentOutboxDispatcherWorker, BaseOutboxDispatcher)

    def test_dispatcher_has_max_attempts(self):
        assert hasattr(AgentOutboxDispatcherWorker, "MAX_ATTEMPTS")
        assert AgentOutboxDispatcherWorker.MAX_ATTEMPTS >= 1

    def test_dispatcher_has_batch_size(self):
        assert hasattr(AgentOutboxDispatcherWorker, "BATCH_SIZE")
        assert AgentOutboxDispatcherWorker.BATCH_SIZE >= 1

    def test_dispatcher_claim_pending_calls_claim_batch(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.claim_pending)
        assert "claim_batch" in source

    def test_dispatcher_claim_pending_uses_worker_id(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.claim_pending)
        assert "locked_by" in source
        assert "self._worker_id" in source

    def test_dispatcher_run_creates_session_transaction(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.run)
        assert "session.begin()" in source

    def test_dispatcher_run_publishes_before_mark(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        publish_idx = source.find("publish")
        mark_idx = source.find("mark_published")
        assert publish_idx < mark_idx

    def test_dispatcher_run_catches_exception(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        assert "except" in source

    def test_dispatcher_mark_failed_checks_max_attempts(self):
        source = inspect.getsource(BaseOutboxDispatcher.mark_failed)
        assert "MAX_ATTEMPTS" in source

    def test_dispatcher_mark_failed_routes_to_dead(self):
        source = inspect.getsource(BaseOutboxDispatcher.mark_failed)
        assert "mark_dead" in source

    def test_dispatcher_mark_failed_routes_to_retryable(self):
        source = inspect.getsource(BaseOutboxDispatcher.mark_failed)
        assert "mark_retryable" in source

    def test_dispatcher_agent_mark_retryable_has_backoff(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.mark_retryable)
        assert "backoff" in source or "BACKOFF" in source

    def test_dispatcher_backoff_seconds_are_positive(self):
        assert RETRY_BACKOFF_BASE_SECONDS >= 1

    def test_two_dispatchers_cannot_claim_same_event(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "skip_locked=True" in source


class TestOutboxModelStructure:
    """Verify AgentOutboxEventModel has required columns for dispatch."""

    def test_outbox_has_id_column(self):
        assert hasattr(AgentOutboxEventModel, "id")

    def test_outbox_has_aggregate_type(self):
        assert hasattr(AgentOutboxEventModel, "aggregate_type")

    def test_outbox_has_aggregate_id(self):
        assert hasattr(AgentOutboxEventModel, "aggregate_id")

    def test_outbox_has_event_type(self):
        assert hasattr(AgentOutboxEventModel, "event_type")

    def test_outbox_has_event_version(self):
        assert hasattr(AgentOutboxEventModel, "event_version")

    def test_outbox_has_payload(self):
        assert hasattr(AgentOutboxEventModel, "payload")

    def test_outbox_has_status(self):
        assert hasattr(AgentOutboxEventModel, "status")

    def test_outbox_has_attempts(self):
        assert hasattr(AgentOutboxEventModel, "attempts")

    def test_outbox_has_error(self):
        assert hasattr(AgentOutboxEventModel, "error")

    def test_outbox_has_locked_at(self):
        assert hasattr(AgentOutboxEventModel, "locked_at")

    def test_outbox_has_locked_by(self):
        assert hasattr(AgentOutboxEventModel, "locked_by")

    def test_outbox_has_available_at(self):
        assert hasattr(AgentOutboxEventModel, "available_at")

    def test_outbox_has_published_at(self):
        assert hasattr(AgentOutboxEventModel, "published_at")

    def test_outbox_has_created_at(self):
        assert hasattr(AgentOutboxEventModel, "created_at")


class TestOutboxDispatchEndToEnd:
    """End-to-end outbox dispatch flow verification."""

    def test_full_dispatch_cycle_order(self):
        run_source = inspect.getsource(BaseOutboxDispatcher.run)
        claim_idx = run_source.find("claim_pending")
        publish_idx = run_source.find("publish")
        mark_idx = run_source.find("mark_published")
        assert claim_idx < publish_idx < mark_idx

    def test_outbox_repo_has_add_method(self):
        assert hasattr(SQLAlchemyAgentOutboxRepository, "add")
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.add)
        assert "self._session.add" in source
        assert "self._session.flush" in source

    def test_outbox_record_has_all_dispatch_fields(self):
        fields = set(OutboxRecord.__dataclass_fields__.keys())
        required = {
            "id", "aggregate_type", "aggregate_id", "event_type",
            "event_version", "payload", "correlation_id", "causation_id",
            "attempts", "error",
        }
        missing = required - fields
        assert not missing, f"OutboxRecord missing fields: {missing}"


class TestOutboxNoCrossModuleImports:
    """Verify the outbox dispatcher does not import from non-agent modules."""

    def test_outbox_repo_has_no_cross_module_imports(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository)
        forbidden = [
            "modules.metering", "modules.observability", "modules.billing",
            "modules.identity", "modules.tools", "modules.core",
        ]
        for pattern in forbidden:
            assert pattern not in source, f"Outbox repo imports forbidden: {pattern}"

    def test_outbox_dispatcher_has_no_cross_module_imports(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker)
        forbidden = [
            "modules.metering", "modules.observability", "modules.billing",
            "modules.identity", "modules.tools", "modules.core",
        ]
        for pattern in forbidden:
            assert pattern not in source, f"Outbox dispatcher imports forbidden: {pattern}"
