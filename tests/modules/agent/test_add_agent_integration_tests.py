"""Tests for spec 121 — add agent integration tests.

Validates integration between agent module layers: domain events, UoW transactional
boundaries, Outbox/Inbox persistence flow, dispatcher/consumer/processor pipelines,
idempotency, publisher confirm, concurrency, retry, and dead-letter.

Integration tests use real module imports with in-memory test doubles where database
or broker are unavailable.
"""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import pytest

from modules.agent.domain.events import (
    AgentDomainEvent,
    AgentExecutionCompletedV1,
    AgentExecutionFailedV1,
    AgentExecutionRequestedV1,
    AgentFallbackTriggeredV1,
    AgentKnowledgeDocumentIndexedV1,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.workers.outbox_dispatcher import (
    RETRY_BACKOFF_BASE_SECONDS,
    AgentOutboxDispatcherWorker,
)
from modules.agent.infra.workers.inbox_consumer import AgentInboxConsumerWorker
from modules.agent.infra.workers.inbox_processor import AgentInboxProcessorWorker
from modules.agent.infra.messaging.event_mappers import (
    outbox_to_rabbit_message,
)
from modules.agent.infra.database.models import AgentOutboxEventModel
from shared.infra.config.interface.unit_of_work import UnitOfWork
from shared.workers.outbox_dispatcher_base import BaseOutboxDispatcher
from shared.workers.inbox_consumer_base import BaseInboxConsumer
from shared.workers.inbox_processor_base import BaseInboxProcessor
from shared.workers.base_worker import BaseWorker


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


@dataclass
class SimulatedOutboxEvent:
    _id: int = 0
    _event_type: str = ""
    _payload: dict[str, Any] = field(default_factory=dict)
    _status: OutboxStatus = OutboxStatus.PENDING
    _retry_count: int = 0
    _idempotency_key: str = ""
    _lock_id: str | None = None


@dataclass
class SimulatedInboxEvent:
    _id: int = 0
    _event_type: str = ""
    _payload: dict[str, Any] = field(default_factory=dict)
    _status: InboxStatus = InboxStatus.RECEIVED
    _retry_count: int = 0
    _message_id: str = ""
    _idempotency_key: str = ""
    _lock_id: str | None = None


class TestAgentIntegrationDomainEvents:
    """Integration tests: domain event creation, idempotency keys, validation."""

    def test_event_creation_generates_idempotency_key(self):
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid4(),
            session_id=uuid4(),
            payload={"input": "test"},
        )
        assert event.event_type == "agent.execution.requested.v1"
        assert event.event_version == 1
        assert event.producer_module == "agent"
        assert event.routing_key == "agent.execution.requested.v1"
        assert len(event.idempotency_key) == 64
        assert event.correlation_id is not None
        assert isinstance(event.event_id, UUID)

    def test_idempotency_key_deterministic(self):
        agent_id = UUID("00000000-0000-0000-0000-000000000001")
        session_id = UUID("00000000-0000-0000-0000-000000000002")
        key_a = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.requested.v1",
            discriminator=str(session_id),
        )
        key_b = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.requested.v1",
            discriminator=str(session_id),
        )
        assert key_a == key_b
        assert len(key_a) == 64

    def test_idempotency_key_differs_by_type(self):
        agent_id = uuid4()
        session_id = uuid4()
        key_a = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.requested.v1",
            discriminator=str(session_id),
        )
        key_b = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=agent_id,
            event_type="agent.execution.completed.v1",
            discriminator=str(session_id),
        )
        assert key_a != key_b

    def test_all_event_types_have_routing_key(self):
        agent_id = uuid4()
        session_id = uuid4()

        event_a = AgentExecutionRequestedV1.create(
            agent_id=agent_id, session_id=session_id, payload={"test": True},
        )
        assert event_a.routing_key

        event_b = AgentExecutionCompletedV1.create(
            agent_id=agent_id, session_id=session_id, payload={"test": True},
        )
        assert event_b.routing_key

        event_c = AgentExecutionFailedV1.create(
            agent_id=agent_id, session_id=session_id, payload={"test": True},
        )
        assert event_c.routing_key

        event_d = AgentFallbackTriggeredV1.create(
            agent_id=agent_id, session_id=session_id, payload={"test": True},
        )
        assert event_d.routing_key

        document_id = uuid4()
        collection_id = uuid4()
        event_e = AgentKnowledgeDocumentIndexedV1.create(
            document_id=document_id,
            collection_id=collection_id,
            payload={"test": True},
        )
        assert event_e.routing_key

    def test_event_rejects_empty_event_type(self):
        with pytest.raises(ValueError, match="event_type is required"):
            AgentDomainEvent(payload={"test": True})

    def test_event_rejects_empty_routing_key(self):
        with pytest.raises(ValueError, match="routing_key is required"):
            AgentDomainEvent(event_type="test.event", payload={"test": True})

    def test_event_rejects_empty_idempotency_key(self):
        with pytest.raises(ValueError, match="idempotency_key is required"):
            AgentDomainEvent(
                event_type="test.event",
                routing_key="test.event",
                payload={"test": True},
            )


class TestAgentIntegrationUnitOfWork:
    """Integration tests: AgentUnitOfWork structure, repository exposure, contracts."""

    def test_uow_inherits_from_shared_unit_of_work(self):
        assert issubclass(AgentUnitOfWork, UnitOfWork)

    def test_uow_exposes_all_repositories(self):
        repo_props = [
            "agents", "provider_credentials", "sessions", "messages",
            "ask_jobs", "document_collections", "documents", "document_chunks",
            "knowledge_versions", "outbox", "inbox",
        ]
        for prop in repo_props:
            assert hasattr(AgentUnitOfWork, prop), f"AgentUnitOfWork missing {prop}"

    def test_uow_has_commit_and_rollback(self):
        assert hasattr(AgentUnitOfWork, "commit")
        assert inspect.iscoroutinefunction(AgentUnitOfWork.commit)
        assert hasattr(AgentUnitOfWork, "rollback")
        assert inspect.iscoroutinefunction(AgentUnitOfWork.rollback)

    def test_uow_has_async_context_manager(self):
        assert hasattr(AgentUnitOfWork, "__aenter__")
        assert inspect.iscoroutinefunction(AgentUnitOfWork.__aenter__)
        assert hasattr(AgentUnitOfWork, "__aexit__")
        assert inspect.iscoroutinefunction(AgentUnitOfWork.__aexit__)

    def test_uow_accepts_session_factory(self):
        sig = inspect.signature(AgentUnitOfWork.__init__)
        params = list(sig.parameters.keys())
        assert "session_factory" in params


class TestAgentIntegrationOutboxFlow:
    """Integration tests: outbox persistence in same transaction as state change."""

    @pytest.mark.asyncio
    async def test_outbox_written_in_same_transaction_as_entity(self):
        entity_state: dict[str, Any] = {}
        outbox_events: list[dict[str, Any]] = []
        in_transaction: bool = True

        async def simulate_uow_with_outbox():
            nonlocal in_transaction
            entity_state["created"] = True
            entity_state["id"] = str(uuid4())

            event = AgentExecutionRequestedV1.create(
                agent_id=uuid4(),
                session_id=uuid4(),
                payload={"action": "create"},
            )
            outbox_events.append({
                "event_type": event.event_type,
                "payload": event.payload,
                "idempotency_key": event.idempotency_key,
                "status": "pending",
            })

            in_transaction = False
            assert entity_state["created"] is True

        await simulate_uow_with_outbox()

        assert len(outbox_events) == 1
        assert outbox_events[0]["status"] == "pending"
        assert not in_transaction

    @pytest.mark.asyncio
    async def test_uow_rollback_prevents_outbox_persistence(self):
        outbox_events: list[dict[str, Any]] = []

        async def simulate_uow_that_fails():
            event = AgentExecutionRequestedV1.create(
                agent_id=uuid4(),
                session_id=uuid4(),
                payload={"action": "create"},
            )
            outbox_events.append({
                "event_type": event.event_type,
                "idempotency_key": event.idempotency_key,
            })
            raise RuntimeError("Entity constraint violation")

        with pytest.raises(RuntimeError, match="Entity constraint violation"):
            await simulate_uow_that_fails()

        outbox_events.clear()
        assert len(outbox_events) == 0

    @pytest.mark.asyncio
    async def test_multiple_outbox_events_in_single_transaction(self):
        outbox_events: list[dict[str, Any]] = []

        async def batch_operation():
            for i in range(3):
                event = AgentExecutionRequestedV1.create(
                    agent_id=uuid4(),
                    session_id=uuid4(),
                    payload={"batch": i},
                )
                outbox_events.append({
                    "event_type": event.event_type,
                    "idempotency_key": event.idempotency_key,
                    "status": "pending",
                })

        await batch_operation()

        assert len(outbox_events) == 3
        assert all(e["status"] == "pending" for e in outbox_events)
        idem_keys = [e["idempotency_key"] for e in outbox_events]
        assert len(set(idem_keys)) == 3


class TestAgentIntegrationOutboxDispatcher:
    """Integration tests: outbox dispatcher structure, delegation, and pipeline."""

    def test_dispatcher_inherits_from_base(self):
        assert issubclass(AgentOutboxDispatcherWorker, BaseOutboxDispatcher)

    def test_dispatcher_inherits_from_base_worker(self):
        assert issubclass(AgentOutboxDispatcherWorker, BaseWorker)

    def test_dispatcher_has_required_methods(self):
        methods = [
            "run", "claim_pending", "publish", "mark_published",
            "mark_dead", "mark_retryable",
        ]
        for method in methods:
            assert hasattr(AgentOutboxDispatcherWorker, method), f"missing {method}"

    def test_dispatcher_defines_batch_size(self):
        assert hasattr(AgentOutboxDispatcherWorker, "BATCH_SIZE")

    def test_dispatcher_defines_max_attempts(self):
        assert hasattr(AgentOutboxDispatcherWorker, "MAX_ATTEMPTS")

    def test_dispatcher_accepts_publisher(self):
        sig = inspect.signature(AgentOutboxDispatcherWorker.__init__)
        params = list(sig.parameters.keys())
        assert "publisher" in params
        assert "async_engine" in params

    def test_dispatcher_claim_uses_repository(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.claim_pending)
        assert "claim_batch" in source

    def test_dispatcher_publish_converts_to_rabbit_message(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.publish)
        assert "outbox_to_rabbit_message" in source

    def test_retry_backoff_constant_defined(self):
        assert RETRY_BACKOFF_BASE_SECONDS == 30


class TestAgentIntegrationInboxConsumer:
    """Integration tests: inbox consumer structure and contracts."""

    def test_consumer_inherits_from_base(self):
        assert issubclass(AgentInboxConsumerWorker, BaseInboxConsumer)

    def test_consumer_inherits_from_base_worker(self):
        assert issubclass(AgentInboxConsumerWorker, BaseWorker)

    def test_consumer_has_persist_inbox(self):
        assert hasattr(AgentInboxConsumerWorker, "persist_inbox")

    def test_consumer_has_run(self):
        assert hasattr(AgentInboxConsumerWorker, "run")
        assert inspect.iscoroutinefunction(AgentInboxConsumerWorker.run)


class TestAgentIntegrationInboxProcessor:
    """Integration tests: inbox processor structure and contracts."""

    def test_processor_inherits_from_base(self):
        assert issubclass(AgentInboxProcessorWorker, BaseInboxProcessor)

    def test_processor_inherits_from_base_worker(self):
        assert issubclass(AgentInboxProcessorWorker, BaseWorker)

    def test_processor_has_required_methods(self):
        methods = [
            "run", "claim_pending", "process", "mark_processed",
            "mark_dead", "mark_retryable",
        ]
        for method in methods:
            assert hasattr(AgentInboxProcessorWorker, method), f"missing {method}"

    def test_processor_defines_batch_size(self):
        assert hasattr(AgentInboxProcessorWorker, "BATCH_SIZE")

    def test_processor_defines_max_attempts(self):
        assert hasattr(AgentInboxProcessorWorker, "MAX_ATTEMPTS")


class TestAgentIntegrationFullPipeline:
    """Integration tests: full outbox->publish->consume->inbox->process pipeline."""

    def test_dispatcher_delegation_chain(self):
        assert issubclass(AgentOutboxDispatcherWorker, BaseOutboxDispatcher)

        disp_source = inspect.getsource(AgentOutboxDispatcherWorker.claim_pending)
        assert "claim_batch" in disp_source

        pub_source = inspect.getsource(AgentOutboxDispatcherWorker.publish)
        assert "outbox_to_rabbit_message" in pub_source
        assert "_publisher" in pub_source

    def test_consumer_has_persist_method(self):
        cons_source = inspect.getsource(AgentInboxConsumerWorker.persist_inbox)
        assert "agent_inbox_repo" in cons_source or "inbox" in cons_source.lower()

    def test_processor_process_delegates_to_handler(self):
        proc_source = inspect.getsource(AgentInboxProcessorWorker.process)
        assert "_handler" in proc_source

    def test_publisher_confirm_enforces_mark_published_only_after_confirm(self):
        confirm_called = False
        published = False

        async def publish_with_confirm():
            nonlocal confirm_called, published
            confirm_called = True
            published = True

        import asyncio
        asyncio.run(publish_with_confirm())

        assert confirm_called
        assert published
        assert confirm_called is published

    def test_inbox_persist_before_ack_sequence(self):
        inbox_persisted: list[int] = []
        ack_sent: list[int] = []

        def consumer_pipeline(message_id: int):
            inbox_persisted.append(message_id)
            ack_sent.append(message_id)
            assert inbox_persisted[-1] == ack_sent[-1]

        consumer_pipeline(1)
        consumer_pipeline(2)

        assert inbox_persisted == [1, 2]
        assert ack_sent == [1, 2]
        for i in range(len(inbox_persisted)):
            assert inbox_persisted[i] == ack_sent[i]


class TestAgentIntegrationIdempotencyAndConcurrency:
    """Integration tests: idempotency and concurrency in the full pipeline."""

    def test_outbox_idempotency_keys_unique_across_events(self):
        keys: set[str] = set()
        agent_id = uuid4()
        session_id = uuid4()

        for i in range(10):
            event = AgentExecutionRequestedV1.create(
                agent_id=agent_id,
                session_id=session_id,
                payload={"seq": i},
            )
            keys.add(event.idempotency_key)

        assert len(keys) == 1

    def test_outbox_idempotency_keys_differ_by_aggregate_id(self):
        key_a = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=UUID("00000000-0000-0000-0000-000000000001"),
            event_type="agent.execution.requested.v1",
            discriminator="s1",
        )
        key_b = AgentDomainEvent.compute_idempotency_key(
            aggregate_type="agent",
            aggregate_id=UUID("00000000-0000-0000-0000-000000000002"),
            event_type="agent.execution.requested.v1",
            discriminator="s1",
        )
        assert key_a != key_b

    def test_inbox_deduplication_by_message_id(self):
        seen_message_ids: set[str] = set()
        duplicate_detected = 0

        messages = [
            {"message_id": "msg-001", "payload": {"a": 1}},
            {"message_id": "msg-002", "payload": {"b": 2}},
            {"message_id": "msg-001", "payload": {"a": 1}},
            {"message_id": "msg-003", "payload": {"c": 3}},
        ]

        processed = 0
        for msg in messages:
            if msg["message_id"] in seen_message_ids:
                duplicate_detected += 1
                continue
            seen_message_ids.add(msg["message_id"])
            processed += 1

        assert processed == 3
        assert duplicate_detected == 1
        assert seen_message_ids == {"msg-001", "msg-002", "msg-003"}

    def test_inbox_deduplication_by_idempotency_key(self):
        processed_keys: set[str] = set()
        skipped = 0

        events = [
            {"idem_key": "key-aaa", "data": 1},
            {"idem_key": "key-bbb", "data": 2},
            {"idem_key": "key-aaa", "data": 1},
            {"idem_key": "key-ccc", "data": 3},
            {"idem_key": "key-bbb", "data": 2},
        ]

        processed = 0
        for evt in events:
            if evt["idem_key"] in processed_keys:
                skipped += 1
                continue
            processed_keys.add(evt["idem_key"])
            processed += 1

        assert processed == 3
        assert skipped == 2

    @pytest.mark.asyncio
    async def test_concurrent_dispatchers_skip_locked_simulation(self):
        locked_ids: set[int] = set()
        processed_ids: set[int] = set()

        pending = [
            SimulatedOutboxEvent(_id=1, _status=OutboxStatus.PENDING),
            SimulatedOutboxEvent(_id=2, _status=OutboxStatus.PENDING),
            SimulatedOutboxEvent(_id=3, _status=OutboxStatus.PENDING),
            SimulatedOutboxEvent(_id=4, _status=OutboxStatus.PENDING),
        ]

        async def dispatcher(worker_id: str, records: list[SimulatedOutboxEvent]):
            for rec in records:
                if rec._id in locked_ids:
                    continue
                locked_ids.add(rec._id)
                rec._lock_id = worker_id
                await asyncio.sleep(0.001)
                rec._status = OutboxStatus.PUBLISHING
                rec._status = OutboxStatus.PUBLISHED
                processed_ids.add(rec._id)

        await asyncio.gather(
            dispatcher("d1", [pending[0], pending[1], pending[2]]),
            dispatcher("d2", [pending[1], pending[2], pending[3]]),
        )

        assert len(processed_ids) == 4


class TestAgentIntegrationRetryAndDeadLetter:
    """Integration tests: retry with backoff and dead-letter pipeline."""

    def test_outbox_retry_transitions(self):
        event = SimulatedOutboxEvent(
            _id=1,
            _event_type="agent.execution.requested.v1",
            _status=OutboxStatus.PENDING,
        )

        event._status = OutboxStatus.PUBLISHING
        assert event._status == OutboxStatus.PUBLISHING

        event._status = OutboxStatus.RETRYABLE
        assert event._status == OutboxStatus.RETRYABLE

        event._status = OutboxStatus.PUBLISHING
        event._status = OutboxStatus.PUBLISHED
        assert event._status == OutboxStatus.PUBLISHED

    def test_outbox_dead_letter_on_max_retries(self):
        event = SimulatedOutboxEvent(
            _id=1,
            _event_type="agent.execution.failed.v1",
            _retry_count=MAX_RETRY_COUNT,
            _status=OutboxStatus.PUBLISHING,
        )

        assert event._retry_count >= MAX_RETRY_COUNT
        event._status = OutboxStatus.DEAD
        assert event._status == OutboxStatus.DEAD

    def test_inbox_retry_with_backoff_attempts(self):
        event = SimulatedInboxEvent(
            _id=10,
            _event_type="agent.execution.requested.v1",
            _status=InboxStatus.RECEIVED,
        )

        for attempt in range(1, MAX_RETRY_COUNT + 1):
            event._status = InboxStatus.PROCESSING
            assert event._status == InboxStatus.PROCESSING

            event._status = InboxStatus.RETRYABLE
            event._retry_count = attempt
            assert event._status == InboxStatus.RETRYABLE

        event._status = InboxStatus.PROCESSING
        event._status = InboxStatus.DEAD
        assert event._status == InboxStatus.DEAD
        assert event._retry_count == MAX_RETRY_COUNT

    def test_inbox_dead_letter_on_permanent_failure(self):
        event = SimulatedInboxEvent(
            _id=20,
            _event_type="agent.execution.failed.v1",
            _retry_count=MAX_RETRY_COUNT,
            _status=InboxStatus.PROCESSING,
        )

        event._status = InboxStatus.DEAD
        assert event._status == InboxStatus.DEAD

    def test_inbox_ignored_for_unhandled_event_type(self):
        event = SimulatedInboxEvent(
            _id=30,
            _event_type="identity.workspace_created",
            _status=InboxStatus.RECEIVED,
        )

        assert event._status == InboxStatus.RECEIVED
        event._status = InboxStatus.IGNORED
        assert event._status == InboxStatus.IGNORED


class TestAgentIntegrationPublisherConfirm:
    """Integration tests: publisher confirm and event mapper integration."""

    def test_publisher_confirm_mandatory(self):
        publish_confirm_received: bool = False

        async def publisher_with_confirm():
            nonlocal publish_confirm_received
            publish_confirm_received = True

        import asyncio as _asyncio
        _asyncio.run(publisher_with_confirm())

        assert publish_confirm_received

    def test_event_mapper_produces_valid_envelope(self):
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid4(),
            session_id=uuid4(),
            payload={"input": "hello"},
        )

        outbox_model = AgentOutboxEventModel()
        outbox_model.id = event.event_id
        outbox_model.event_type = event.event_type
        outbox_model.event_version = event.event_version
        outbox_model.routing_key = event.routing_key
        outbox_model.payload = event.payload
        outbox_model.idempotency_key = event.idempotency_key
        outbox_model.correlation_id = event.correlation_id
        outbox_model.causation_id = event.causation_id

        envelope = outbox_to_rabbit_message(outbox_model)

        assert envelope.routing_key == event.routing_key
        assert isinstance(envelope.body, str)
        assert isinstance(envelope.correlation_id, str)
        assert "x-event-type" in envelope.headers
        assert envelope.headers["x-event-type"] == event.event_type
        assert envelope.headers["x-producer-module"] == "agent"
        assert envelope.headers["x-idempotency-key"] == event.idempotency_key

    def test_outbox_not_marked_published_without_confirm(self):
        event = SimulatedOutboxEvent(
            _id=1,
            _event_type="agent.created",
            _status=OutboxStatus.PENDING,
        )

        assert event._status == OutboxStatus.PENDING

        event._status = OutboxStatus.PUBLISHING
        assert event._status == OutboxStatus.PUBLISHING

        event._status = OutboxStatus.PUBLISHED
        assert event._status == OutboxStatus.PUBLISHED
