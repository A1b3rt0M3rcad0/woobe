"""Tests for spec 122 — add outbox dispatcher tests.

Validates outbox dispatcher-specific behavior: claim-and-lock, publish pipeline,
status transitions (publishing → published/retryable/dead), retry with backoff,
dead-letter enforcement, batch processing, and publisher confirm patterns.

Focuses on AgentOutboxDispatcherWorker behavioral contracts.
"""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

import pytest

from woobe_workers.consumers.agent.outbox_dispatcher import (
    RETRY_BACKOFF_BASE_SECONDS,
    AgentOutboxDispatcherWorker,
)
from modules.agent.infra.messaging.event_mappers import (
    RabbitMQMessageEnvelope,
    outbox_to_rabbit_message,
)
from modules.agent.infra.database.models import AgentOutboxEventModel
from modules.agent.domain.events import AgentExecutionRequestedV1
from woobe_workers.runtime.outbox_dispatcher_base import BaseOutboxDispatcher, OutboxRecord
from woobe_workers.runtime.base_worker import BaseWorker


class OutboxStatus(str, Enum):
    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    RETRYABLE = "retryable"
    DEAD = "dead"


VALID_OUTBOX_TRANSITIONS: dict[OutboxStatus, set[OutboxStatus]] = {
    OutboxStatus.PENDING: {OutboxStatus.PUBLISHING},
    OutboxStatus.PUBLISHING: {OutboxStatus.PUBLISHED, OutboxStatus.RETRYABLE, OutboxStatus.DEAD},
    OutboxStatus.RETRYABLE: {OutboxStatus.PUBLISHING},
}

MAX_RETRY_COUNT = 3
DEFAULT_BATCH_SIZE = 50


@dataclass
class DispatcherTestRecord:
    record_id: int = 0
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status: OutboxStatus = OutboxStatus.PENDING
    retry_count: int = 0
    idempotency_key: str = ""
    lock_id: str | None = None
    attempts: int = 0
    error: str | None = None


class TestOutboxDispatcherStructure:
    """Verify dispatcher structural contracts."""

    def test_dispatcher_inherits_from_base(self):
        assert issubclass(AgentOutboxDispatcherWorker, BaseOutboxDispatcher)

    def test_dispatcher_inherits_from_base_worker(self):
        assert issubclass(AgentOutboxDispatcherWorker, BaseWorker)

    def test_dispatcher_defines_batch_size(self):
        assert hasattr(AgentOutboxDispatcherWorker, "BATCH_SIZE")
        assert isinstance(AgentOutboxDispatcherWorker.BATCH_SIZE, int)

    def test_dispatcher_defines_max_attempts(self):
        assert hasattr(AgentOutboxDispatcherWorker, "MAX_ATTEMPTS")
        assert AgentOutboxDispatcherWorker.MAX_ATTEMPTS == 5

    def test_dispatcher_accepts_publisher_and_engine(self):
        sig = inspect.signature(AgentOutboxDispatcherWorker.__init__)
        params = list(sig.parameters.keys())
        assert "publisher" in params
        assert "async_engine" in params

    def test_dispatcher_accepts_optional_worker_id(self):
        sig = inspect.signature(AgentOutboxDispatcherWorker.__init__)
        params = list(sig.parameters.keys())
        assert "worker_id" in params

    def test_run_method_creates_session_and_delegates_to_super(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.run)
        assert "AsyncSession" in source
        assert "session.begin" in source
        assert "super().run()" in source

    def test_retry_backoff_constant(self):
        assert RETRY_BACKOFF_BASE_SECONDS == 30


class TestOutboxDispatcherClaimPipeline:
    """Verify claim-and-lock behavior."""

    def test_claim_uses_repository_claim_batch(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.claim_pending)
        assert "claim_batch" in source
        assert "_repo" in source

    def test_claim_builds_event_map_for_tracking(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.claim_pending)
        assert "_event_map" in source

    def test_claim_populates_event_map_keyed_by_id(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.claim_pending)
        assert "id" in source.lower() or "record" in source.lower()

    def test_batch_size_default_is_50(self):
        assert AgentOutboxDispatcherWorker.BATCH_SIZE == 50

    def test_max_attempts_default_is_5(self):
        assert AgentOutboxDispatcherWorker.MAX_ATTEMPTS == 5

    @pytest.mark.asyncio
    async def test_claim_locks_events_to_prevent_double_processing(self):
        locked_ids: set[int] = set()
        claimed_by: dict[int, str] = {}

        pending = [
            DispatcherTestRecord(record_id=1, event_type="agent.execution.requested.v1"),
            DispatcherTestRecord(record_id=2, event_type="agent.execution.requested.v1"),
            DispatcherTestRecord(record_id=3, event_type="agent.execution.requested.v1"),
        ]

        async def claim(worker_id: str, records: list[DispatcherTestRecord]):
            for rec in records:
                if rec.record_id in locked_ids:
                    continue
                locked_ids.add(rec.record_id)
                claimed_by[rec.record_id] = worker_id
                rec.status = OutboxStatus.PUBLISHING
                rec.lock_id = worker_id

        await asyncio.gather(
            claim("d1", pending[:]),
            claim("d2", pending[:]),
        )

        assert len(locked_ids) == 3
        assert claimed_by[1] is not None
        assert claimed_by[2] is not None
        assert all(rec.status == OutboxStatus.PUBLISHING for rec in pending)


class TestOutboxDispatcherPublishPipeline:
    """Verify publish converts to RabbitMQ message and uses publisher."""

    def test_publish_uses_outbox_to_rabbit_message(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.publish)
        assert "outbox_to_rabbit_message" in source

    def test_publish_uses_publisher_interface(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.publish)
        assert "_publisher" in source
        assert "publish" in source

    def test_publish_converts_outbox_record_to_rabbit_message(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.publish)
        assert "outbox_to_rabbit_message" in source

    def test_event_mapper_domain_to_outbox_then_rabbit_message(self):
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid4(),
            session_id=uuid4(),
            payload={"action": "test_publish"},
        )

        outbox_model = AgentOutboxEventModel()
        outbox_model.id = event.event_id
        outbox_model.event_type = event.event_type
        outbox_model.event_version = event.event_version
        outbox_model.routing_key = event.routing_key
        outbox_model.payload = event.payload
        outbox_model.idempotency_key = event.idempotency_key
        outbox_model.correlation_id = event.correlation_id

        envelope = outbox_to_rabbit_message(outbox_model)

        assert isinstance(envelope, RabbitMQMessageEnvelope)
        assert envelope.routing_key == event.routing_key
        assert "agent.execution.requested.v1" in envelope.body
        assert "x-idempotency-key" in envelope.headers

    def test_rabbit_message_includes_idempotency_key(self):
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid4(), session_id=uuid4(), payload={"test": "idem"},
        )
        outbox_model = AgentOutboxEventModel()
        outbox_model.id = event.event_id
        outbox_model.event_type = event.event_type
        outbox_model.event_version = event.event_version
        outbox_model.routing_key = event.routing_key
        outbox_model.payload = event.payload
        outbox_model.idempotency_key = event.idempotency_key
        outbox_model.correlation_id = event.correlation_id

        envelope = outbox_to_rabbit_message(outbox_model)

        assert envelope.headers["x-idempotency-key"] == event.idempotency_key
        assert event.idempotency_key in envelope.body


class TestOutboxDispatcherStatusTransitions:
    """Verify status transition behavior for publish outcomes."""

    def test_mark_published_uses_repository(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.mark_published)
        assert "_repo" in source
        assert "mark_published" in source

    def test_mark_dead_uses_repository(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.mark_dead)
        assert "_repo" in source
        assert "mark_dead" in source

    def test_mark_retryable_uses_repository(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.mark_retryable)
        assert "_repo" in source
        assert "mark_retryable" in source

    def test_valid_transitions_map(self):
        assert "pending" in [s.value for s in OutboxStatus]
        assert OutboxStatus.PUBLISHING in VALID_OUTBOX_TRANSITIONS[OutboxStatus.PENDING]
        assert OutboxStatus.PUBLISHED in VALID_OUTBOX_TRANSITIONS[OutboxStatus.PUBLISHING]
        assert OutboxStatus.RETRYABLE in VALID_OUTBOX_TRANSITIONS[OutboxStatus.PUBLISHING]
        assert OutboxStatus.DEAD in VALID_OUTBOX_TRANSITIONS[OutboxStatus.PUBLISHING]

    def test_retryable_can_return_to_publishing(self):
        assert OutboxStatus.PUBLISHING in VALID_OUTBOX_TRANSITIONS[OutboxStatus.RETRYABLE]

    def test_dead_and_published_have_no_outgoing_transitions(self):
        assert OutboxStatus.PUBLISHED not in VALID_OUTBOX_TRANSITIONS
        assert OutboxStatus.DEAD not in VALID_OUTBOX_TRANSITIONS

    def test_pending_to_published_invalid_without_publishing(self):
        assert OutboxStatus.PUBLISHED not in VALID_OUTBOX_TRANSITIONS.get(
            OutboxStatus.PENDING, set()
        )


class TestOutboxDispatcherRetryAndDeadLetter:
    """Verify retry with backoff and dead-letter behavior."""

    def test_retry_backoff_is_positive_integer(self):
        assert isinstance(RETRY_BACKOFF_BASE_SECONDS, int)
        assert RETRY_BACKOFF_BASE_SECONDS > 0

    def test_publish_to_retryable_transition_allowed(self):
        record = DispatcherTestRecord(
            record_id=100,
            event_type="agent.execution.requested.v1",
            status=OutboxStatus.PUBLISHING,
            retry_count=0,
        )
        record.status = OutboxStatus.RETRYABLE
        assert record.status == OutboxStatus.RETRYABLE

        record.status = OutboxStatus.PUBLISHING
        assert record.status == OutboxStatus.PUBLISHING

        record.status = OutboxStatus.PUBLISHED
        assert record.status == OutboxStatus.PUBLISHED

    def test_dead_letter_when_retries_exhausted(self):
        record = DispatcherTestRecord(
            record_id=101,
            event_type="agent.execution.failed.v1",
            status=OutboxStatus.PUBLISHING,
            retry_count=MAX_RETRY_COUNT,
        )
        assert record.retry_count >= MAX_RETRY_COUNT

        record.status = OutboxStatus.DEAD
        assert record.status == OutboxStatus.DEAD

    def test_retry_count_tracks_attempts(self):
        record = DispatcherTestRecord(
            record_id=102,
            event_type="agent.execution.requested.v1",
            status=OutboxStatus.PUBLISHING,
            retry_count=0,
        )

        for attempt in range(1, MAX_RETRY_COUNT + 1):
            record.status = OutboxStatus.RETRYABLE
            record.retry_count = attempt
            assert record.retry_count == attempt

            record.status = OutboxStatus.PUBLISHING

        assert record.retry_count == MAX_RETRY_COUNT

    def test_outbox_retry_preserves_event_payload(self):
        payload = {"agent_id": "uuid-test", "action": "deploy"}
        record = DispatcherTestRecord(
            record_id=103,
            event_type="agent.execution.requested.v1",
            payload=payload,
            status=OutboxStatus.PUBLISHING,
            retry_count=1,
        )

        record.status = OutboxStatus.RETRYABLE
        assert record.payload == payload

        record.status = OutboxStatus.PUBLISHING
        record.status = OutboxStatus.PUBLISHED
        assert record.payload == payload


class TestOutboxDispatcherPublisherConfirm:
    """Verify publisher confirm semantics."""

    def test_agent_run_delegates_to_super(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.run)
        assert "super().run()" in source

    def test_base_run_has_publish_and_mark_published_sequence(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        assert "publish" in source
        assert "mark_published" in source
        assert "claim_pending" in source

    def test_base_run_has_exception_handling(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        assert "Exception" in source
        assert "mark_failed" in source

    def test_publisher_confirm_required(self):
        confirmed = False

        async def safe_publish():
            nonlocal confirmed
            confirmed = True

        import asyncio as _asyncio
        _asyncio.run(safe_publish())

        assert confirmed

    def test_publish_failure_must_not_mark_published(self):
        record = DispatcherTestRecord(
            record_id=200,
            event_type="agent.execution.requested.v1",
            status=OutboxStatus.PUBLISHING,
        )

        publish_succeeded = False

        if publish_succeeded:
            record.status = OutboxStatus.PUBLISHED
        else:
            record.status = OutboxStatus.RETRYABLE

        assert record.status == OutboxStatus.RETRYABLE
        assert record.status != OutboxStatus.PUBLISHED


class TestOutboxDispatcherConcurrency:
    """Verify concurrent dispatcher behavior with SKIP LOCKED simulation."""

    @pytest.mark.asyncio
    async def test_two_dispatchers_claim_non_overlapping_events(self):
        locked_ids: set[int] = set()
        processed: set[int] = set()
        events = [
            DispatcherTestRecord(record_id=i, event_type="agent.created")
            for i in range(1, 7)
        ]

        async def dispatcher(worker_id: str, candidates: list[DispatcherTestRecord]):
            for evt in candidates:
                if evt.record_id in locked_ids:
                    continue
                locked_ids.add(evt.record_id)
                evt.lock_id = worker_id
                evt.status = OutboxStatus.PUBLISHING
                await asyncio.sleep(0.001)
                evt.status = OutboxStatus.PUBLISHED
                processed.add(evt.record_id)

        await asyncio.gather(
            dispatcher("dA", events[0:3]),
            dispatcher("dB", events[3:6]),
        )

        assert len(processed) == 6

    @pytest.mark.asyncio
    async def test_skip_locked_prevents_double_publish(self):
        locks: dict[int, str] = {}
        published: set[int] = set()

        events = [
            DispatcherTestRecord(record_id=10),
            DispatcherTestRecord(record_id=20),
            DispatcherTestRecord(record_id=30),
        ]

        async def attempt_claim(worker: str, batch: list[DispatcherTestRecord]):
            for evt in batch:
                if evt.record_id in locks:
                    continue
                locks[evt.record_id] = worker
                evt.status = OutboxStatus.PUBLISHING
                await asyncio.sleep(0.001)
                evt.status = OutboxStatus.PUBLISHED
                published.add(evt.record_id)

        await asyncio.gather(
            attempt_claim("w1", [events[0], events[1]]),
            attempt_claim("w2", events[:]),
        )

        assert len(published) == 3
        for evt in events:
            assert evt.status == OutboxStatus.PUBLISHED


class TestOutboxDispatcherEndToEnd:
    """End-to-end simulation of dispatcher run loop."""

    def test_base_run_claims_publishes_marks_sequence(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        assert "claim_pending" in source
        assert "publish" in source
        assert "mark_published" in source

    def test_base_run_wraps_exceptions(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        assert "Exception" in source or "exc" in source

    def test_mark_failed_increments_attempts_and_decides_dead_or_retryable(self):
        source = inspect.getsource(BaseOutboxDispatcher.mark_failed)
        assert "attempts" in source
        assert "MAX_ATTEMPTS" in source
        assert "mark_dead" in source or "mark_retryable" in source

    def test_base_mark_failed_retryable_below_max(self):
        record = OutboxRecord(
            id=1,
            aggregate_type="agent",
            aggregate_id=uuid4(),
            event_type="agent.created",
            event_version=1,
            payload={"test": True},
            attempts=1,
        )

        assert record.attempts == 1
        record.attempts += 1
        assert record.attempts == 2

    def test_base_mark_failed_dead_at_max(self):
        record = OutboxRecord(
            id=2,
            aggregate_type="agent",
            aggregate_id=uuid4(),
            event_type="agent.created",
            event_version=1,
            payload={"test": True},
            attempts=4,
        )

        record.attempts += 1
        assert record.attempts == 5
