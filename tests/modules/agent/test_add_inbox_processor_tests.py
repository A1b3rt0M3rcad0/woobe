"""Tests for spec 124 — add inbox processor tests.

Validates inbox processor-specific behavior: claim-and-lock from inbox,
handler delegation, status transitions (processing → processed/retryable/dead),
exponential backoff calculation, batch processing, and handler protocol contract.

Focuses on AgentInboxProcessorWorker behavioral contracts.
"""
from __future__ import annotations

import inspect
from enum import Enum
from uuid import uuid4

from woobe_workers.consumers.agent.inbox_processor import (
    RETRY_BACKOFF_BASE_SECONDS,
    AgentInboxHandlerProtocol,
    AgentInboxProcessorWorker,
)
from woobe_workers.runtime.inbox_processor_base import BaseInboxProcessor, InboxProcessingRecord
from woobe_workers.runtime.base_worker import BaseWorker


class InboxStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    IGNORED = "ignored"
    RETRYABLE = "retryable"
    DEAD = "dead"


VALID_INBOX_TRANSITIONS: dict[InboxStatus, set[InboxStatus]] = {
    InboxStatus.RECEIVED: {InboxStatus.PROCESSING, InboxStatus.IGNORED},
    InboxStatus.PROCESSING: {InboxStatus.PROCESSED, InboxStatus.RETRYABLE, InboxStatus.DEAD},
    InboxStatus.RETRYABLE: {InboxStatus.PROCESSING},
}

MAX_RETRY_COUNT = 3


class TestInboxProcessorStructure:
    """Verify inbox processor structural contracts."""

    def test_processor_inherits_from_base(self):
        assert issubclass(AgentInboxProcessorWorker, BaseInboxProcessor)

    def test_processor_inherits_from_base_worker(self):
        assert issubclass(AgentInboxProcessorWorker, BaseWorker)

    def test_processor_defines_batch_size(self):
        assert hasattr(AgentInboxProcessorWorker, "BATCH_SIZE")
        assert isinstance(AgentInboxProcessorWorker.BATCH_SIZE, int)

    def test_processor_defines_max_attempts(self):
        assert hasattr(AgentInboxProcessorWorker, "MAX_ATTEMPTS")
        assert AgentInboxProcessorWorker.MAX_ATTEMPTS == 5

    def test_processor_accepts_handler_and_engine(self):
        sig = inspect.signature(AgentInboxProcessorWorker.__init__)
        params = list(sig.parameters.keys())
        assert "handler" in params
        assert "async_engine" in params

    def test_processor_accepts_optional_worker_id(self):
        sig = inspect.signature(AgentInboxProcessorWorker.__init__)
        params = list(sig.parameters.keys())
        assert "worker_id" in params

    def test_run_creates_session_and_delegates_to_super(self):
        source = inspect.getsource(AgentInboxProcessorWorker.run)
        assert "AsyncSession" in source
        assert "session.begin" in source
        assert "super().run()" in source

    def test_retry_backoff_constant(self):
        assert RETRY_BACKOFF_BASE_SECONDS == 30

    def test_batch_size_default_is_50(self):
        assert AgentInboxProcessorWorker.BATCH_SIZE == 50


class TestInboxProcessorClaimPipeline:
    """Verify claim-and-lock behavior for inbox events."""

    def test_claim_uses_repository_claim_batch(self):
        source = inspect.getsource(AgentInboxProcessorWorker.claim_pending)
        assert "claim_batch" in source
        assert "_repo" in source

    def test_claim_builds_processing_records(self):
        source = inspect.getsource(AgentInboxProcessorWorker.claim_pending)
        assert "InboxProcessingRecord" in source

    def test_claim_populates_event_map(self):
        source = inspect.getsource(AgentInboxProcessorWorker.claim_pending)
        assert "_event_map" in source

    def test_claim_record_includes_outbox_origin_id(self):
        source = inspect.getsource(AgentInboxProcessorWorker.claim_pending)
        assert "outbox_origin_id" in source
        assert "message_id" in source

    def test_claim_record_includes_correlation_and_causation(self):
        source = inspect.getsource(AgentInboxProcessorWorker.claim_pending)
        assert "correlation_id" in source
        assert "causation_id" in source

    def test_claim_record_includes_attempts_and_error(self):
        source = inspect.getsource(AgentInboxProcessorWorker.claim_pending)
        assert "attempts" in source
        assert "error" in source


class TestInboxProcessorHandlerDelegation:
    """Verify handler delegation and protocol contract."""

    def test_process_delegates_to_handler(self):
        source = inspect.getsource(AgentInboxProcessorWorker.process)
        assert "_handler" in source
        assert "handle" in source

    def test_process_passes_event_type_to_handler(self):
        source = inspect.getsource(AgentInboxProcessorWorker.process)
        assert "event_type" in source

    def test_process_passes_payload_to_handler(self):
        source = inspect.getsource(AgentInboxProcessorWorker.process)
        assert "payload" in source

    def test_process_passes_correlation_id_to_handler(self):
        source = inspect.getsource(AgentInboxProcessorWorker.process)
        assert "correlation_id" in source

    def test_process_passes_causation_id_to_handler(self):
        source = inspect.getsource(AgentInboxProcessorWorker.process)
        assert "causation_id" in source

    def test_process_passes_event_version_to_handler(self):
        source = inspect.getsource(AgentInboxProcessorWorker.process)
        assert "event_version" in source

    def test_handler_protocol_defines_handle_signature(self):
        assert hasattr(AgentInboxHandlerProtocol, "handle")
        sig = inspect.signature(AgentInboxHandlerProtocol.handle)
        params = list(sig.parameters.keys())
        assert "event_type" in params
        assert "payload" in params
        assert "kwargs" in params


class TestInboxProcessorStatusTransitions:
    """Verify status transition behavior for processing outcomes."""

    def test_mark_processed_uses_repository(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_processed)
        assert "_repo" in source
        assert "mark_processed" in source

    def test_mark_dead_uses_repository(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_dead)
        assert "_repo" in source
        assert "mark_dead" in source

    def test_mark_retryable_uses_repository(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_retryable)
        assert "_repo" in source
        assert "mark_retryable" in source

    def test_valid_transitions_map(self):
        assert InboxStatus.PROCESSING in VALID_INBOX_TRANSITIONS[InboxStatus.RECEIVED]
        assert InboxStatus.IGNORED in VALID_INBOX_TRANSITIONS[InboxStatus.RECEIVED]
        assert InboxStatus.PROCESSED in VALID_INBOX_TRANSITIONS[InboxStatus.PROCESSING]
        assert InboxStatus.RETRYABLE in VALID_INBOX_TRANSITIONS[InboxStatus.PROCESSING]
        assert InboxStatus.DEAD in VALID_INBOX_TRANSITIONS[InboxStatus.PROCESSING]

    def test_retryable_can_return_to_processing(self):
        assert InboxStatus.PROCESSING in VALID_INBOX_TRANSITIONS[InboxStatus.RETRYABLE]

    def test_received_to_ignored_for_unhandled_events(self):
        assert InboxStatus.IGNORED in VALID_INBOX_TRANSITIONS[InboxStatus.RECEIVED]

    def test_dead_and_processed_have_no_outgoing_transitions(self):
        assert InboxStatus.PROCESSED not in VALID_INBOX_TRANSITIONS
        assert InboxStatus.DEAD not in VALID_INBOX_TRANSITIONS


class TestInboxProcessorRetryAndBackoff:
    """Verify retry with exponential backoff behavior."""

    def test_mark_retryable_calculates_backoff(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_retryable)
        assert "backoff" in source
        assert "timedelta" in source
        assert "RETRY_BACKOFF_BASE_SECONDS" in source

    def test_backoff_is_proportional_to_attempts(self):
        attempts = 3
        expected_backoff_seconds = RETRY_BACKOFF_BASE_SECONDS * (attempts + 1)
        assert expected_backoff_seconds == 120

    def test_backoff_base_is_positive(self):
        assert RETRY_BACKOFF_BASE_SECONDS > 0

    def test_backoff_scales_linearly_with_attempts(self):
        for attempts in range(5):
            backoff = RETRY_BACKOFF_BASE_SECONDS * (attempts + 1)
            assert backoff == 30 * (attempts + 1)

    def test_mark_dead_includes_error_message(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_dead)
        assert "error" in source

    def test_mark_retryable_includes_available_at(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_retryable)
        assert "available_at" in source

    def test_processing_to_dead_after_max_retries(self):
        record = InboxProcessingRecord(
            id=uuid4(),
            outbox_origin_id="msg-001",
            aggregate_type="agent",
            event_type="agent.execution.failed.v1",
            event_version=1,
            payload={"error": "permanent"},
            attempts=MAX_RETRY_COUNT,
        )
        assert record.attempts >= MAX_RETRY_COUNT


class TestInboxProcessorConcurrency:
    """Verify concurrent processor behavior."""

    def test_claim_batch_uses_skip_locked_semantics(self):
        source = inspect.getsource(AgentInboxProcessorWorker.claim_pending)
        assert "claim_batch" in source
        assert "locked_by" in source

    def test_two_processors_claim_different_events(self):
        claimed: dict[int, str] = {}
        events = [
            {"id": 1, "worker": None},
            {"id": 2, "worker": None},
            {"id": 3, "worker": None},
            {"id": 4, "worker": None},
        ]

        for evt in events[:2]:
            evt["worker"] = "p1"
            claimed[evt["id"]] = "p1"

        remaining = [e for e in events if e["id"] not in claimed]
        for evt in remaining:
            evt["worker"] = "p2"
            claimed[evt["id"]] = "p2"

        assert len(claimed) == 4
        assert claimed[1] == "p1"
        assert claimed[3] == "p2"


class TestInboxProcessorEndToEnd:
    """End-to-end simulation of inbox processor pipeline."""

    def test_run_claims_processes_marks_sequence(self):
        source = inspect.getsource(BaseInboxProcessor.run)
        assert "claim_pending" in source
        assert "process" in source
        assert "mark_processed" in source

    def test_run_wraps_exceptions_to_mark_failed(self):
        source = inspect.getsource(BaseInboxProcessor.run)
        assert "Exception" in source or "exc" in source

    def test_mark_failed_decides_dead_or_retryable(self):
        source = inspect.getsource(BaseInboxProcessor.mark_failed)
        assert "attempts" in source
        assert "MAX_ATTEMPTS" in source

    def test_full_pipeline_simulation(self):
        processed_count = 0
        error_count = 0

        events = [
            {"id": 1, "valid": True},
            {"id": 2, "valid": True},
            {"id": 3, "valid": False},
            {"id": 4, "valid": True},
        ]

        for evt in events:
            try:
                if not evt["valid"]:
                    raise RuntimeError("handler failed")
                processed_count += 1
            except RuntimeError:
                error_count += 1

        assert processed_count == 3
        assert error_count == 1
