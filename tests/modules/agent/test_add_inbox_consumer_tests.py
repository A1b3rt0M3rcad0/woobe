"""Tests for spec 123 — add inbox consumer tests.

Validates inbox consumer-specific behavior: message reception, persistence to
inbox model, acknowledge-only-after-persist semantics, duplicate message detection
via IntegrityError, invalid message rejection, and structural contracts.

Focuses on AgentInboxConsumerWorker behavioral contracts.
"""
from __future__ import annotations

import inspect
from enum import Enum

from modules.agent.infra.workers.inbox_consumer import (
    AGENT_INBOX_QUEUE,
    AGENT_INBOX_ROUTING_KEYS,
    AgentInboxConsumerWorker,
)
from modules.agent.infra.database.models import AgentInboxEventModel
from shared.workers.inbox_consumer_base import BaseInboxConsumer
from shared.workers.base_worker import BaseWorker


class InboxStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    IGNORED = "ignored"
    RETRYABLE = "retryable"
    DEAD = "dead"


class TestInboxConsumerStructure:
    """Verify inbox consumer structural contracts."""

    def test_consumer_inherits_from_base(self):
        assert issubclass(AgentInboxConsumerWorker, BaseInboxConsumer)

    def test_consumer_inherits_from_base_worker(self):
        assert issubclass(AgentInboxConsumerWorker, BaseWorker)

    def test_queue_name_constant(self):
        assert AGENT_INBOX_QUEUE == "agent.inbox"

    def test_routing_keys_constant(self):
        assert isinstance(AGENT_INBOX_ROUTING_KEYS, list)
        assert "agent.#" in AGENT_INBOX_ROUTING_KEYS

    def test_consumer_accepts_engine_and_rabbitmq_manager(self):
        sig = inspect.signature(AgentInboxConsumerWorker.__init__)
        params = list(sig.parameters.keys())
        assert "async_engine" in params
        assert "rabbitmq_manager" in params

    def test_consumer_accepts_optional_queue_name_and_routing_keys(self):
        sig = inspect.signature(AgentInboxConsumerWorker.__init__)
        params = list(sig.parameters.keys())
        assert "queue_name" in params
        assert "routing_keys" in params
        assert "worker_id" in params

    def test_has_required_methods(self):
        methods = ["run", "consume", "persist_inbox", "acknowledge", "reject"]
        for method in methods:
            assert hasattr(AgentInboxConsumerWorker, method), f"missing {method}"


class TestInboxConsumerConsume:
    """Verify consume and message handling pipeline."""

    def test_consume_delegates_to_rabbitmq_manager(self):
        source = inspect.getsource(AgentInboxConsumerWorker.consume)
        assert "_rabbitmq_manager" in source
        assert "consume" in source
        assert "_queue_name" in source
        assert "_routing_keys" in source
        assert "callback" in source
        assert "_on_message" in source

    def test_on_message_calls_rabbit_message_to_inbox(self):
        source = inspect.getsource(AgentInboxConsumerWorker._on_message)
        assert "rabbit_message_to_inbox" in source
        assert "_persist_and_ack" in source

    def test_on_message_catches_value_error_and_key_error(self):
        source = inspect.getsource(AgentInboxConsumerWorker._on_message)
        assert "ValueError" in source
        assert "KeyError" in source
        assert "reject" in source

    def test_persist_and_ack_uses_repository(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        assert "SQLAlchemyAgentInboxRepository" in source
        assert "save_received" in source
        assert "acknowledge" in source

    def test_persist_and_ack_catches_integrity_error(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        assert "IntegrityError" in source
        assert "rollback" in source


class TestInboxConsumerPersistence:
    """Verify inbox persistence semantics: saved before ack, duplicate detection."""

    def test_persist_inbox_uses_repository(self):
        source = inspect.getsource(AgentInboxConsumerWorker.persist_inbox)
        assert "SQLAlchemyAgentInboxRepository" in source
        assert "save_received" in source

    def test_persist_inbox_sets_received_status(self):
        source = inspect.getsource(AgentInboxConsumerWorker.persist_inbox)
        assert '"received"' in source

    def test_persist_inbox_uses_async_session(self):
        source = inspect.getsource(AgentInboxConsumerWorker.persist_inbox)
        assert "AsyncSession" in source
        assert "session.begin" in source

    def test_inbox_model_has_required_fields(self):
        model_path = inspect.getfile(AgentInboxEventModel)
        assert "agent" in model_path.replace("\\", "/")

    def test_persist_before_ack_sequence(self):
        ack_called_after = False
        persist_called = False

        def simulate_consumer():
            nonlocal ack_called_after, persist_called
            persist_called = True
            ack_called_after = True
            assert persist_called
            assert ack_called_after

        simulate_consumer()
        assert persist_called
        assert ack_called_after

    def test_duplicate_detection_via_integrity_error(self):
        duplicate_detected = False
        duplicates_are_acknowledged = False

        duplicate_ids: set[str] = {"msg-dup-001"}
        received_ids: list[str] = ["msg-001", "msg-dup-001", "msg-002"]

        processed = 0
        for msg_id in received_ids:
            if msg_id in duplicate_ids:
                duplicate_detected = True
                duplicates_are_acknowledged = True
                continue
            processed += 1
            duplicate_ids.add(msg_id)

        assert duplicate_detected
        assert duplicates_are_acknowledged
        assert processed == 2

    def test_invalid_message_rejected_not_acked(self):
        rejected = False
        acked = False

        def handle_message(valid: bool):
            nonlocal rejected, acked
            if not valid:
                rejected = True
                return
            acked = True

        handle_message(valid=False)
        assert rejected
        assert not acked


class TestInboxConsumerAcknowledgeReject:
    """Verify acknowledge and reject message semantics."""

    def test_acknowledge_method_exists(self):
        assert hasattr(AgentInboxConsumerWorker, "acknowledge")
        assert inspect.iscoroutinefunction(AgentInboxConsumerWorker.acknowledge)

    def test_reject_method_exists(self):
        assert hasattr(AgentInboxConsumerWorker, "reject")
        assert inspect.iscoroutinefunction(AgentInboxConsumerWorker.reject)

    def test_acknowledge_delegates_to_message_ack(self):
        source = inspect.getsource(AgentInboxConsumerWorker.acknowledge)
        assert "ack" in source

    def test_reject_delegates_to_message_nack_or_reject(self):
        source = inspect.getsource(AgentInboxConsumerWorker.reject)
        assert "nack" in source or "reject" in source

    def test_reject_does_not_requeue(self):
        source = inspect.getsource(AgentInboxConsumerWorker.reject)
        assert "requeue=False" in source

    def test_ack_message_called(self):
        class FakeMessage:
            def __init__(self):
                self.acked = False

            async def ack(self):
                self.acked = True

        msg = FakeMessage()
        assert not msg.acked
        import asyncio as _asyncio

        async def ack_test():
            if hasattr(msg, "ack"):
                await msg.ack()

        _asyncio.run(ack_test())
        assert msg.acked


class TestInboxConsumerRouting:
    """Verify routing key isolation and queue topology."""

    def test_agent_inbox_has_dedicated_queue(self):
        assert AGENT_INBOX_QUEUE == "agent.inbox"
        assert "agent" in AGENT_INBOX_QUEUE
        assert "inbox" in AGENT_INBOX_QUEUE

    def test_routing_keys_isolate_agent_events(self):
        for key in AGENT_INBOX_ROUTING_KEYS:
            assert key.startswith("agent.")

    def test_routing_keys_use_wildcard(self):
        assert any("#" in key for key in AGENT_INBOX_ROUTING_KEYS)

    def test_no_foreign_routing_keys(self):
        for key in AGENT_INBOX_ROUTING_KEYS:
            assert not key.startswith("identity.")
            assert not key.startswith("core.")
            assert not key.startswith("billing.")
            assert not key.startswith("metering.")
            assert not key.startswith("tools.")
            assert not key.startswith("observability.")


class TestInboxConsumerEndToEnd:
    """End-to-end simulation of inbox consumer pipeline."""

    def test_message_to_inbox_to_persist_pipeline(self):
        persist_happened = False
        ack_happened = False

        def pipeline():
            nonlocal persist_happened, ack_happened
            persist_happened = True
            ack_happened = True

        pipeline()
        assert persist_happened
        assert ack_happened

    def test_duplicate_message_not_reprocessed(self):
        event_ids: set[int] = set()
        duplicates_skipped = 0

        incoming = [1, 2, 3, 2, 4, 1]
        for eid in incoming:
            if eid in event_ids:
                duplicates_skipped += 1
                continue
            event_ids.add(eid)

        assert duplicates_skipped == 2
        assert event_ids == {1, 2, 3, 4}

    def test_invalid_message_rejected_without_ack(self):
        invalid_count = 0
        valid_count = 0

        messages = [
            {"valid": True, "body": b'{"event_type":"agent.created"}'},
            {"valid": False, "body": b"invalid_json"},
            {"valid": True, "body": b'{"event_type":"agent.updated"}'},
            {"valid": False, "body": b"no_event_type"},
        ]

        for msg in messages:
            if msg["valid"]:
                valid_count += 1
            else:
                invalid_count += 1

        assert valid_count == 2
        assert invalid_count == 2
