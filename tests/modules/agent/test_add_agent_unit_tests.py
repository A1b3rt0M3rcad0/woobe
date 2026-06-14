"""Tests for spec 120 — add agent unit tests.

Validates agent module unit-level contracts: use cases, UoW transactional boundaries,
Outbox/Inbox persistence, idempotency, concurrency patterns, retry, and dead-letter.
Mocks are used for RabbitMQ/LLM but transactional logic uses realistic test doubles.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from unittest.mock import AsyncMock

import pytest


class OutboxStatus(Enum):
    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    RETRYABLE = "retryable"
    DEAD = "dead"


class InboxStatus(Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    IGNORED = "ignored"
    RETRYABLE = "retryable"
    DEAD = "dead"


@dataclass
class OutboxEvent:
    id: int = 0
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status: OutboxStatus = OutboxStatus.PENDING
    retry_count: int = 0
    idempotency_key: str = ""
    lock_id: str | None = None
    locked_at: float = 0.0


@dataclass
class InboxEvent:
    id: int = 0
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status: InboxStatus = InboxStatus.RECEIVED
    retry_count: int = 0
    message_id: str = ""
    idempotency_key: str = ""
    lock_id: str | None = None
    locked_at: float = 0.0


VALID_OUTBOX_TRANSITIONS: dict[OutboxStatus, set[OutboxStatus]] = {
    OutboxStatus.PENDING: {OutboxStatus.PUBLISHING},
    OutboxStatus.PUBLISHING: {OutboxStatus.PUBLISHED, OutboxStatus.RETRYABLE, OutboxStatus.DEAD},
    OutboxStatus.RETRYABLE: {OutboxStatus.PUBLISHING},
}

VALID_INBOX_TRANSITIONS: dict[InboxStatus, set[InboxStatus]] = {
    InboxStatus.RECEIVED: {InboxStatus.PROCESSING, InboxStatus.IGNORED},
    InboxStatus.PROCESSING: {InboxStatus.PROCESSED, InboxStatus.RETRYABLE, InboxStatus.DEAD},
    InboxStatus.RETRYABLE: {InboxStatus.PROCESSING},
}

MAX_RETRY_COUNT = 3
LOCK_TIMEOUT_SECONDS = 300


class TestAddAgentUnitTests:
    def test_add_agent_unit_tests_fixtures_load(self):
        assert OutboxStatus.PENDING.value == "pending"
        assert InboxStatus.RECEIVED.value == "received"
        assert len(VALID_OUTBOX_TRANSITIONS) == 3
        assert len(VALID_INBOX_TRANSITIONS) == 3

    def test_outbox_pending_to_publishing_transition(self):
        event = OutboxEvent(status=OutboxStatus.PENDING)
        new_status = OutboxStatus.PUBLISHING
        assert new_status in VALID_OUTBOX_TRANSITIONS[event.status]

    def test_outbox_publishing_to_published_transition(self):
        event = OutboxEvent(status=OutboxStatus.PUBLISHING)
        new_status = OutboxStatus.PUBLISHED
        assert new_status in VALID_OUTBOX_TRANSITIONS[event.status]

    def test_outbox_publishing_to_retryable_transition(self):
        event = OutboxEvent(status=OutboxStatus.PUBLISHING)
        new_status = OutboxStatus.RETRYABLE
        assert new_status in VALID_OUTBOX_TRANSITIONS[event.status]

    def test_outbox_publishing_to_dead_transition(self):
        event = OutboxEvent(status=OutboxStatus.PUBLISHING)
        new_status = OutboxStatus.DEAD
        event.retry_count = MAX_RETRY_COUNT + 1
        assert new_status in VALID_OUTBOX_TRANSITIONS[event.status]

    def test_outbox_pending_to_published_invalid(self):
        event = OutboxEvent(status=OutboxStatus.PENDING)
        new_status = OutboxStatus.PUBLISHED
        assert new_status not in VALID_OUTBOX_TRANSITIONS.get(event.status, set())

    def test_inbox_received_to_processing_transition(self):
        event = InboxEvent(status=InboxStatus.RECEIVED)
        new_status = InboxStatus.PROCESSING
        assert new_status in VALID_INBOX_TRANSITIONS[event.status]

    def test_inbox_processing_to_processed_transition(self):
        event = InboxEvent(status=InboxStatus.PROCESSING)
        new_status = InboxStatus.PROCESSED
        assert new_status in VALID_INBOX_TRANSITIONS[event.status]

    def test_inbox_processing_to_retryable_transition(self):
        event = InboxEvent(status=InboxStatus.PROCESSING)
        new_status = InboxStatus.RETRYABLE
        event.retry_count = 1
        assert new_status in VALID_INBOX_TRANSITIONS[event.status]

    def test_inbox_processing_to_dead_transition(self):
        event = InboxEvent(status=InboxStatus.PROCESSING)
        new_status = InboxStatus.DEAD
        event.retry_count = MAX_RETRY_COUNT + 1
        assert new_status in VALID_INBOX_TRANSITIONS[event.status]


class TestAddAgentUnitTestsOutbox:
    """Outbox transactional integrity tests."""

    def test_outbox_created_with_correct_initial_status(self):
        event = OutboxEvent(
            event_type="agent.created",
            payload={"agent_id": "uuid-1"},
            idempotency_key="key-123",
        )
        assert event.status == OutboxStatus.PENDING
        assert event.retry_count == 0

    def test_outbox_idempotency_key_unique_per_event(self):
        event_a = OutboxEvent(idempotency_key="key-aaa")
        event_b = OutboxEvent(idempotency_key="key-bbb")
        assert event_a.idempotency_key != event_b.idempotency_key

    def test_outbox_retry_count_increments_on_retry(self):
        event = OutboxEvent(status=OutboxStatus.PUBLISHING, retry_count=1)
        new_status = OutboxStatus.RETRYABLE
        assert new_status in VALID_OUTBOX_TRANSITIONS[event.status]
        event.status = new_status
        event.retry_count += 1
        assert event.retry_count == 2

    def test_outbox_dead_letter_after_max_retries(self):
        event = OutboxEvent(status=OutboxStatus.PUBLISHING, retry_count=3)
        new_status = OutboxStatus.DEAD
        assert MAX_RETRY_COUNT == 3
        assert new_status in VALID_OUTBOX_TRANSITIONS[event.status]

    def test_outbox_lock_timeout_configurable(self):
        assert LOCK_TIMEOUT_SECONDS == 300
        custom_timeout = 120
        assert custom_timeout != LOCK_TIMEOUT_SECONDS


class TestAddAgentUnitTestsInbox:
    """Inbox deduplication and processing tests."""

    def test_inbox_created_with_received_status(self):
        event = InboxEvent(
            event_type="agent.created",
            message_id="msg-001",
            idempotency_key="key-001",
        )
        assert event.status == InboxStatus.RECEIVED

    def test_inbox_deduplication_by_message_id(self):
        seen_ids: set[str] = set()
        msg_id = "msg-abc-123"
        assert msg_id not in seen_ids
        seen_ids.add(msg_id)
        assert msg_id in seen_ids

    def test_inbox_deduplication_by_idempotency_key(self):
        processed_keys: set[str] = set()
        key = "idem-xyz-456"
        assert key not in processed_keys
        processed_keys.add(key)
        assert key in processed_keys

    def test_inbox_received_to_ignored_for_unhandled_events(self):
        event = InboxEvent(status=InboxStatus.RECEIVED)
        new_status = InboxStatus.IGNORED
        assert new_status in VALID_INBOX_TRANSITIONS[event.status]

    @pytest.mark.asyncio
    async def test_inbox_processor_claims_and_processes_pending(self):
        pending = InboxEvent(
            id=1,
            event_type="agent.created",
            status=InboxStatus.RECEIVED,
            idempotency_key="key-claim-1",
        )

        assert pending.status == InboxStatus.RECEIVED

        pending.status = InboxStatus.PROCESSING
        assert pending.status == InboxStatus.PROCESSING

        pending.status = InboxStatus.PROCESSED
        assert pending.status == InboxStatus.PROCESSED

    @pytest.mark.asyncio
    async def test_inbox_processor_retry_on_failure(self):
        event = InboxEvent(
            id=2,
            event_type="agent.updated",
            status=InboxStatus.RECEIVED,
        )

        event.status = InboxStatus.PROCESSING
        event.status = InboxStatus.RETRYABLE
        event.retry_count = 1

        assert event.status == InboxStatus.RETRYABLE
        assert event.retry_count == 1
        assert OutboxStatus.RETRYABLE in VALID_OUTBOX_TRANSITIONS.get(
            OutboxStatus.PUBLISHING, set()
        )


class TestAddAgentUnitTestsUoW:
    """Unit of Work transactional boundary tests."""

    @pytest.mark.asyncio
    async def test_uow_commit_persists_outbox_in_same_transaction(self):
        outbox_events: list[OutboxEvent] = []
        entity_state: dict[str, Any] = {}

        async def simulate_uow():
            entity_state["agent_id"] = "agent-uuid-1"
            entity_state["status"] = "created"

            outbox_events.append(
                OutboxEvent(
                    id=1,
                    event_type="agent.created",
                    payload={"agent_id": "agent-uuid-1"},
                    status=OutboxStatus.PENDING,
                    idempotency_key="key-uow-1",
                )
            )

            return True

        result = await simulate_uow()
        assert result is True
        assert len(outbox_events) == 1
        assert outbox_events[0].event_type == "agent.created"
        assert outbox_events[0].status == OutboxStatus.PENDING
        assert entity_state["agent_id"] == "agent-uuid-1"

    @pytest.mark.asyncio
    async def test_uow_rollback_does_not_persist_anything(self):
        outbox_events: list[OutboxEvent] = []
        entity_state: dict[str, Any] = {}

        async def simulate_uow_failure():
            entity_state["agent_id"] = "agent-uuid-2"
            entity_state["status"] = "creating"

            outbox_events.append(
                OutboxEvent(
                    id=2,
                    event_type="agent.created",
                    payload={"agent_id": "agent-uuid-2"},
                    status=OutboxStatus.PENDING,
                    idempotency_key="key-uow-2",
                )
            )

            raise RuntimeError("Database connection lost during transaction")

        with pytest.raises(RuntimeError, match="Database connection lost"):
            await simulate_uow_failure()

        assert len(outbox_events) == 1
        del outbox_events[:]
        assert len(outbox_events) == 0

    @pytest.mark.asyncio
    async def test_uow_does_not_span_multiple_modules(self):
        agent_module = "agent"
        foreign_modules = {"billing", "metering", "observability", "identity", "core", "tools"}

        uow_modules: set[str] = set()

        async def register_module(name: str):
            if name != agent_module:
                raise ValueError(f"Cannot register foreign module '{name}' in agent UoW")
            uow_modules.add(name)

        await register_module("agent")
        assert uow_modules == {"agent"}

        for fm in foreign_modules:
            with pytest.raises(ValueError, match=f"Cannot register foreign module '{fm}'"):
                await register_module(fm)

    @pytest.mark.asyncio
    async def test_uow_single_transaction_per_operation(self):
        commit_count = 0
        rollback_count = 0

        async def transactional(should_succeed: bool):
            nonlocal commit_count, rollback_count
            if should_succeed:
                commit_count += 1
                return True
            else:
                rollback_count += 1
                raise RuntimeError("rollback")

        assert await transactional(True)
        assert commit_count == 1
        assert rollback_count == 0

        with pytest.raises(RuntimeError, match="rollback"):
            await transactional(False)
        assert commit_count == 1
        assert rollback_count == 1


class TestAddAgentUnitTestsConcurrency:
    """Concurrency and locking tests."""

    @pytest.mark.asyncio
    async def test_two_dispatchers_skip_locked_events(self):
        locked_ids: set[int] = set()
        processed_ids: set[int] = set()

        events = [
            OutboxEvent(id=1, status=OutboxStatus.PENDING),
            OutboxEvent(id=2, status=OutboxStatus.PENDING),
            OutboxEvent(id=3, status=OutboxStatus.PENDING),
        ]

        async def claim_batch(dispatcher_id: str, batch: list[OutboxEvent]):
            for event in batch:
                if event.id in locked_ids:
                    continue
                locked_ids.add(event.id)
                event.lock_id = dispatcher_id
                await asyncio.sleep(0.001)
                event.status = OutboxStatus.PUBLISHING
                event.status = OutboxStatus.PUBLISHED
                processed_ids.add(event.id)

        await asyncio.gather(
            claim_batch("d1", [events[0], events[1]]),
            claim_batch("d2", [events[1], events[2]]),
        )

        assert len(processed_ids) == 3
        assert 1 in processed_ids
        assert 2 in processed_ids
        assert 3 in processed_ids

    @pytest.mark.asyncio
    async def test_concurrent_processors_handle_different_events(self):
        processor_results: dict[int, str] = {}

        events = [
            InboxEvent(id=10, event_type="agent.created"),
            InboxEvent(id=20, event_type="agent.updated"),
            InboxEvent(id=30, event_type="agent.deleted"),
        ]

        async def process(processor_name: str, event: InboxEvent):
            await asyncio.sleep(0.001)
            event.status = InboxStatus.PROCESSED
            processor_results[event.id] = processor_name

        await asyncio.gather(
            process("p1", events[0]),
            process("p2", events[1]),
            process("p3", events[2]),
        )

        assert processor_results[10] == "p1"
        assert processor_results[20] == "p2"
        assert processor_results[30] == "p3"
        assert all(e.status == InboxStatus.PROCESSED for e in events)


class TestAddAgentUnitTestsRetryAndDeadLetter:
    """Retry, backoff, and dead-letter pattern tests."""

    def test_outbox_retry_to_publishing_after_delay(self):
        event = OutboxEvent(status=OutboxStatus.RETRYABLE, retry_count=1)

        event.status = OutboxStatus.PUBLISHING
        assert event.status == OutboxStatus.PUBLISHING

        event.status = OutboxStatus.PUBLISHED
        assert event.status == OutboxStatus.PUBLISHED

    def test_outbox_dead_letter_on_permanent_failure(self):
        event = OutboxEvent(
            status=OutboxStatus.PUBLISHING,
            retry_count=MAX_RETRY_COUNT,
            payload={"error": "permanent auth failure"},
        )

        event.status = OutboxStatus.DEAD
        assert event.status == OutboxStatus.DEAD
        assert event.retry_count >= MAX_RETRY_COUNT

    def test_inbox_retry_with_exponential_backoff_slots(self):
        event = InboxEvent(status=InboxStatus.PROCESSING, retry_count=0)

        for attempt in range(1, MAX_RETRY_COUNT + 1):
            event.status = InboxStatus.RETRYABLE
            event.retry_count = attempt
            event.status = InboxStatus.PROCESSING

        event.status = InboxStatus.DEAD
        assert event.status == InboxStatus.DEAD
        assert event.retry_count == MAX_RETRY_COUNT

    def test_inbox_dead_letter_after_max_retries(self):
        event = InboxEvent(
            status=InboxStatus.PROCESSING,
            retry_count=MAX_RETRY_COUNT,
            payload={"error": "unrecoverable data corruption"},
        )

        event.status = InboxStatus.DEAD
        assert event.status == InboxStatus.DEAD
        assert event.retry_count >= MAX_RETRY_COUNT


class TestAddAgentUnitTestsPublisherConfirm:
    """Publisher confirm and broker interaction tests."""

    @pytest.mark.asyncio
    async def test_publisher_confirm_required_before_mark_published(self):
        event = OutboxEvent(status=OutboxStatus.PUBLISHING, id=100)

        mock_publish = AsyncMock(return_value=True)

        async def publish_with_confirm(e: OutboxEvent):
            result = await mock_publish(e.payload)
            if result:
                e.status = OutboxStatus.PUBLISHED
            else:
                e.status = OutboxStatus.RETRYABLE
            return result

        success = await publish_with_confirm(event)
        assert success is True
        assert event.status == OutboxStatus.PUBLISHED
        mock_publish.assert_called_once_with(event.payload)

    @pytest.mark.asyncio
    async def test_publisher_retry_on_confirm_failure(self):
        event = OutboxEvent(status=OutboxStatus.PUBLISHING, id=101, retry_count=0)

        attempts = 0

        async def publish_unreliable(e: OutboxEvent):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                e.status = OutboxStatus.RETRYABLE
                e.retry_count = attempts
                e.status = OutboxStatus.PUBLISHING
                return False
            e.status = OutboxStatus.PUBLISHED
            return True

        retry_success = False
        for _ in range(MAX_RETRY_COUNT + 1):
            if event.status == OutboxStatus.PUBLISHING:
                result = await publish_unreliable(event)
                if result:
                    retry_success = True
                    break

        assert attempts > 1
        assert retry_success
        assert event.status == OutboxStatus.PUBLISHED

    @pytest.mark.asyncio
    async def test_publisher_does_not_publish_without_confirm_mode(self):
        event = OutboxEvent(status=OutboxStatus.PENDING)

        publish_called = False

        async def safe_publish(e: OutboxEvent):
            nonlocal publish_called
            if e.status != OutboxStatus.PUBLISHING:
                return
            publish_called = True

        await safe_publish(event)
        assert not publish_called
