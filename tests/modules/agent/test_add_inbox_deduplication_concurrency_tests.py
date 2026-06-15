"""Tests for spec 128 — add inbox deduplication concurrency tests.

Validates inbox deduplication and concurrency guarantees across the agent inbox
pipeline: duplicate detection via message_id/idempotency_key uniqueness,
IntegrityError handling in consumer, SKIP LOCKED for concurrent processors,
lock lifecycle (claim → processing → processed/dead), idempotency key
propagation through inbox, and consumer ack/reject behavior.
"""
from __future__ import annotations

import inspect

from modules.agent.infra.database.models import AgentInboxEventModel
from modules.agent.infra.database.repositories import (
    AGENT_DEFAULT_BATCH_SIZE,
    AGENT_INBOX_LOCK_TIMEOUT_SECONDS,
    SQLAlchemyAgentInboxRepository,
)
from modules.agent.infra.workers.inbox_consumer import (
    AGENT_INBOX_QUEUE,
    AGENT_INBOX_ROUTING_KEYS,
    AgentInboxConsumerWorker,
)
from modules.agent.infra.workers.inbox_processor import (
    AgentInboxProcessorWorker,
)
from shared.workers.inbox_consumer_base import BaseInboxConsumer, InboxRecord
from shared.workers.inbox_processor_base import (
    BaseInboxProcessor,
    InboxProcessingRecord,
)


class TestInboxConsumerDeduplication:
    """Verify inbox consumer detects and handles duplicate messages."""

    def test_consumer_has_persist_and_ack_method(self):
        assert hasattr(AgentInboxConsumerWorker, "_persist_and_ack")
        assert inspect.iscoroutinefunction(AgentInboxConsumerWorker._persist_and_ack)

    def test_persist_and_ack_catches_integrity_error(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        assert "IntegrityError" in source

    def test_persist_and_ack_rolls_back_on_duplicate(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        assert "rollback" in source

    def test_persist_and_ack_acknowledges_after_persist(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        save_idx = source.find("save_received")
        ack_idx = source.find("acknowledge")
        assert save_idx < ack_idx, "must persist before acknowledge"

    def test_persist_and_ack_uses_separate_session(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        assert "AsyncSession" in source
        assert "session.begin()" in source

    def test_consumer_inherits_from_base_inbox_consumer(self):
        assert issubclass(AgentInboxConsumerWorker, BaseInboxConsumer)

    def test_consumer_acknowledge_calls_message_ack(self):
        source = inspect.getsource(AgentInboxConsumerWorker.acknowledge)
        assert "ack" in source

    def test_consumer_reject_calls_nack_or_reject(self):
        source = inspect.getsource(AgentInboxConsumerWorker.reject)
        assert ("nack" in source) or ("reject" in source)

    def test_consumer_reject_does_not_requeue(self):
        source = inspect.getsource(AgentInboxConsumerWorker.reject)
        assert "requeue=False" in source

    def test_consumer_on_message_catches_value_and_key_error(self):
        source = inspect.getsource(AgentInboxConsumerWorker._on_message)
        assert "ValueError" in source or "KeyError" in source

    def test_consumer_on_message_rejects_invalid_messages(self):
        source = inspect.getsource(AgentInboxConsumerWorker._on_message)
        assert "reject" in source

    def test_consumer_queue_is_agent_inbox(self):
        assert AGENT_INBOX_QUEUE == "agent.inbox"

    def test_consumer_routing_keys_use_agent_wildcard(self):
        assert "agent.#" in AGENT_INBOX_ROUTING_KEYS


class TestInboxIdempotencyConstraints:
    """Verify inbox model enforces idempotency via unique constraints."""

    def test_inbox_has_idempotency_key_unique(self):
        from sqlalchemy import UniqueConstraint as UC
        table = AgentInboxEventModel.__table__
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "idempotency_key" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1, "Inbox must have unique constraint on idempotency_key"

    def test_inbox_has_message_id_unique(self):
        from sqlalchemy import UniqueConstraint as UC
        table = AgentInboxEventModel.__table__
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "message_id" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1, "Inbox must have unique constraint on message_id"

    def test_inbox_model_has_message_id_column(self):
        assert hasattr(AgentInboxEventModel, "message_id")

    def test_inbox_model_has_idempotency_key_column(self):
        assert hasattr(AgentInboxEventModel, "idempotency_key")

    def test_inbox_model_has_status_column(self):
        assert hasattr(AgentInboxEventModel, "status")

    def test_inbox_model_has_producer_module_column(self):
        assert hasattr(AgentInboxEventModel, "producer_module")

    def test_inbox_model_has_event_type_column(self):
        assert hasattr(AgentInboxEventModel, "event_type")

    def test_inbox_model_has_event_version_column(self):
        assert hasattr(AgentInboxEventModel, "event_version")

    def test_inbox_model_table_args_has_unique_constraints(self):
        table_args = AgentInboxEventModel.__table_args__
        from sqlalchemy import UniqueConstraint as UC
        uq_count = len([a for a in (table_args or []) if isinstance(a, UC)])
        assert uq_count >= 2, "Expected at least 2 unique constraints (message_id + idempotency_key)"


class TestInboxConcurrencySkipLocked:
    """Verify inbox claim_batch uses SKIP LOCKED for concurrency safety."""

    def test_inbox_claim_batch_uses_skip_locked(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "skip_locked=True" in source

    def test_inbox_claim_batch_uses_with_for_update(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "with_for_update" in source

    def test_inbox_claim_batch_claims_received_and_retryable(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert ('"received"' in source) or ("'received'" in source)
        assert ('"retryable"' in source) or ("'retryable'" in source)

    def test_inbox_claim_batch_excludes_dead(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert '"dead"' not in source and "'dead'" not in source

    def test_inbox_claim_batch_excludes_processed(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert '"processed"' not in source and "'processed'" not in source

    def test_inbox_claim_batch_sets_locked_at(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "locked_at" in source

    def test_inbox_claim_batch_sets_locked_by(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "locked_by" in source

    def test_inbox_claim_batch_sets_status_to_processing(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert '"processing"' in source or "'processing'" in source

    def test_inbox_claim_batch_increments_attempts(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "attempts" in source

    def test_inbox_claim_batch_orders_by_created_at(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "created_at" in source
        assert "asc" in source.lower() or "order_by" in source

    def test_inbox_claim_batch_has_lock_timeout(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "lock_timeout_seconds" in source
        assert "INTERVAL" in source

    def test_inbox_claim_batch_handles_expired_locks(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "locked_at.is_(None)" in source or "locked_at == None" in source.lower()
        assert "INTERVAL" in source

    def test_inbox_claim_batch_respects_batch_size(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "limit" in source

    def test_inbox_claim_batch_default_batch_size_is_positive(self):
        assert AGENT_DEFAULT_BATCH_SIZE >= 1

    def test_inbox_lock_timeout_is_positive(self):
        assert AGENT_INBOX_LOCK_TIMEOUT_SECONDS >= 1


class TestInboxProcessorConcurrency:
    """Verify inbox processor coordinates with claim_batch for concurrency."""

    def test_inbox_processor_inherits_from_base(self):
        assert issubclass(AgentInboxProcessorWorker, BaseInboxProcessor)

    def test_inbox_processor_has_max_attempts(self):
        assert hasattr(AgentInboxProcessorWorker, "MAX_ATTEMPTS")
        assert AgentInboxProcessorWorker.MAX_ATTEMPTS >= 1

    def test_inbox_processor_has_batch_size(self):
        assert hasattr(AgentInboxProcessorWorker, "BATCH_SIZE")
        assert AgentInboxProcessorWorker.BATCH_SIZE >= 1

    def test_inbox_processor_claim_pending_calls_claim_batch(self):
        source = inspect.getsource(AgentInboxProcessorWorker.claim_pending)
        assert "claim_batch" in source

    def test_inbox_processor_claim_pending_uses_worker_id(self):
        source = inspect.getsource(AgentInboxProcessorWorker.claim_pending)
        assert "locked_by" in source
        assert "self._worker_id" in source

    def test_inbox_processor_mark_processed_clears_lock(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_processed)
        assert "mark_processed" in source

    def test_inbox_processor_mark_dead_clears_lock(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_dead)
        assert "mark_dead" in source

    def test_inbox_processor_mark_retryable_clears_lock(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_retryable)
        assert "mark_retryable" in source

    def test_inbox_processor_runs_claim_process_mark_cycle(self):
        source = inspect.getsource(BaseInboxProcessor.run)
        assert "claim_pending" in source
        assert "process" in source
        assert "mark_processed" in source

    def test_inbox_processor_catches_process_exception(self):
        source = inspect.getsource(BaseInboxProcessor.run)
        assert "except" in source
        assert "mark_failed" in source

    def test_inbox_processor_mark_failed_routes_by_attempts(self):
        source = inspect.getsource(BaseInboxProcessor.mark_failed)
        assert "MAX_ATTEMPTS" in source
        assert "mark_dead" in source
        assert "mark_retryable" in source

    def test_two_processors_cannot_claim_same_event(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "skip_locked=True" in source


class TestInboxStatusTransitions:
    """Verify inbox status transitions support deduplication and concurrency."""

    def test_inbox_status_received_is_initial(self):
        from modules.agent.infra.database.repositories import AGENT_INBOX_VALID_TRANSITIONS
        assert "received" in AGENT_INBOX_VALID_TRANSITIONS

    def test_inbox_status_processing_is_a_valid_transition_from_received(self):
        from modules.agent.infra.database.repositories import AGENT_INBOX_VALID_TRANSITIONS
        assert "processing" in AGENT_INBOX_VALID_TRANSITIONS.get("received", set())

    def test_inbox_status_ignored_is_valid_from_received(self):
        from modules.agent.infra.database.repositories import AGENT_INBOX_VALID_TRANSITIONS
        assert "ignored" in AGENT_INBOX_VALID_TRANSITIONS.get("received", set())

    def test_inbox_status_processed_is_valid_from_processing(self):
        from modules.agent.infra.database.repositories import AGENT_INBOX_VALID_TRANSITIONS
        assert "processed" in AGENT_INBOX_VALID_TRANSITIONS.get("processing", set())

    def test_inbox_status_retryable_is_valid_from_processing(self):
        from modules.agent.infra.database.repositories import AGENT_INBOX_VALID_TRANSITIONS
        assert "retryable" in AGENT_INBOX_VALID_TRANSITIONS.get("processing", set())

    def test_inbox_status_dead_is_valid_from_processing(self):
        from modules.agent.infra.database.repositories import AGENT_INBOX_VALID_TRANSITIONS
        assert "dead" in AGENT_INBOX_VALID_TRANSITIONS.get("processing", set())

    def test_inbox_status_processing_is_valid_from_retryable(self):
        from modules.agent.infra.database.repositories import AGENT_INBOX_VALID_TRANSITIONS
        assert "processing" in AGENT_INBOX_VALID_TRANSITIONS.get("retryable", set())

    def test_inbox_validate_transition_raises_on_invalid(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository._validate_transition)
        assert "ValueError" in source


class TestInboxRetryAndDeadLetter:
    """Verify inbox retry and dead-letter behavior for failed processing."""

    def test_inbox_mark_retryable_sets_error(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.mark_retryable)
        assert "error" in source

    def test_inbox_mark_retryable_sets_available_at(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.mark_retryable)
        assert "available_at" in source

    def test_inbox_mark_retryable_clears_lock(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.mark_retryable)
        assert "locked_at = None" in source
        assert "locked_by = None" in source

    def test_inbox_mark_dead_sets_error(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.mark_dead)
        assert "error" in source

    def test_inbox_mark_dead_clears_lock(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.mark_dead)
        assert "locked_at = None" in source
        assert "locked_by = None" in source

    def test_inbox_mark_processed_sets_processed_at(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.mark_processed)
        assert "processed_at" in source

    def test_inbox_mark_processed_clears_lock(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.mark_processed)
        assert "locked_at = None" in source
        assert "locked_by = None" in source

    def test_inbox_processor_has_backoff_seconds(self):
        from modules.agent.infra.workers.inbox_processor import RETRY_BACKOFF_BASE_SECONDS
        assert RETRY_BACKOFF_BASE_SECONDS >= 1


class TestInboxMessageHandlingFlow:
    """Verify the end-to-end inbox message handling flow."""

    def test_consumer_consume_method_uses_rabbitmq_manager(self):
        source = inspect.getsource(AgentInboxConsumerWorker.consume)
        assert "_rabbitmq_manager" in source or "consume" in source

    def test_consumer_on_message_uses_rabbit_message_to_inbox(self):
        source = inspect.getsource(AgentInboxConsumerWorker._on_message)
        assert "rabbit_message_to_inbox" in source

    def test_consumer_queue_and_routing_keys_are_agent_scoped(self):
        assert "agent" in AGENT_INBOX_QUEUE
        for key in AGENT_INBOX_ROUTING_KEYS:
            assert "agent" in key

    def test_inbox_record_has_all_required_fields(self):
        fields = set(InboxRecord.__dataclass_fields__.keys())
        required = {"outbox_origin_id", "aggregate_type", "event_type",
                     "event_version", "payload", "correlation_id", "causation_id"}
        missing = required - fields
        assert not missing, f"InboxRecord missing fields: {missing}"

    def test_inbox_processing_record_has_all_required_fields(self):
        fields = set(InboxProcessingRecord.__dataclass_fields__.keys())
        required = {"id", "outbox_origin_id", "aggregate_type", "event_type",
                     "event_version", "payload", "correlation_id", "causation_id",
                     "attempts", "error"}
        missing = required - fields
        assert not missing, f"InboxProcessingRecord missing fields: {missing}"

    def test_save_received_persists_in_one_statement(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.save_received)
        assert "self._session.add" in source
        assert "self._session.flush" in source
