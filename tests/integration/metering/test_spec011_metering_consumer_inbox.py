"""Tests for spec 011: metering RabbitMQ consumer and inbox.

Covers: broker->inbox persistence, duplicate handling, DB failure,
invalid envelope rejection, binding exactness.
"""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from modules.metering.infra.database.models import InboxEventModel
from modules.metering.infra.messaging.event_mappers import rabbit_message_to_inbox
from modules.metering.infra.workers.inbox_consumer import (
    METERING_INBOX_ROUTING_KEYS,
    MeteringInboxConsumerWorker,
)
from modules.metering.infra.workers.registry import register_metering_workers


@pytest.fixture
def mock_engine():
    return AsyncMock()


@pytest.fixture
def mock_rabbitmq():
    manager = AsyncMock()
    manager.consume = AsyncMock()
    return manager


@pytest.fixture
def sample_message():
    """Create a message mock that simulates an agent.execution.requested.v1 event."""
    payload = {
        "event_id": str(uuid4()),
        "event_type": "agent.execution.requested.v1",
        "event_version": 1,
        "producer_module": "agent",
        "routing_key": "agent.execution.requested.v1",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {"execution_id": str(uuid4()), "agent_id": str(uuid4())},
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "causation_id": str(uuid4()),
        "metadata": {},
    }
    message = MagicMock()
    message.body = json.dumps(payload).encode()
    message.routing_key = "agent.execution.requested.v1"
    message.correlation_id = payload["correlation_id"]
    message.headers = {
        "x-event-type": "agent.execution.requested.v1",
        "x-event-version": "1",
        "x-producer-module": "agent",
        "x-idempotency-key": payload["idempotency_key"],
    }
    message.message_id = str(uuid4())
    message.ack = AsyncMock()
    message.nack = AsyncMock()
    return message


class TestBrokerToInbox:
    """Messages from RabbitMQ must be persisted to the inbox table."""

    @pytest.mark.asyncio
    async def test_rabbit_message_maps_to_inbox_model(self, sample_message):
        """rabbit_message_to_inbox produces a valid InboxEventModel."""
        model = rabbit_message_to_inbox(sample_message)
        assert isinstance(model, InboxEventModel)
        assert model.event_type == "agent.execution.requested.v1"
        assert model.event_version == 1
        assert model.producer_module == "agent"
        assert model.consumer_module == "metering"
        assert model.routing_key == "agent.execution.requested.v1"
        assert model.status == "received"
        assert model.idempotency_key is not None
        assert model.correlation_id is not None
        assert model.causation_id is not None
        assert model.payload is not None
        assert "execution_id" in model.payload

    @pytest.mark.asyncio
    async def test_consumer_consume_calls_rabbitmq(self, mock_engine, mock_rabbitmq):
        """Consumer.consume registers callback with RabbitMQ."""
        consumer = MeteringInboxConsumerWorker(
            async_engine=mock_engine,
            rabbitmq_manager=mock_rabbitmq,
        )
        await consumer.consume()
        assert mock_rabbitmq.consume.await_count == 1

    @pytest.mark.asyncio
    async def test_consumer_routing_keys_are_exact(self):
        """Consumer only binds agent.execution.* routing keys, not metering.#."""
        for key in METERING_INBOX_ROUTING_KEYS:
            assert key.startswith("agent.execution.")
        assert all(key.endswith(".v1") for key in METERING_INBOX_ROUTING_KEYS)
        assert not any(key == "metering.#" for key in METERING_INBOX_ROUTING_KEYS)

    @pytest.mark.asyncio
    async def test_consumer_persists_and_acks_through_integration(self, mock_engine, mock_rabbitmq, sample_message):
        """Consumer creates inbox model and ACKs the message.

        Uses a monkey-patched _persist_and_ack to isolate from real DB.
        """
        consumer = MeteringInboxConsumerWorker(
            async_engine=mock_engine,
            rabbitmq_manager=mock_rabbitmq,
        )
        persist_called = False

        async def fake_persist(message, model):
            nonlocal persist_called
            persist_called = True
            assert model.event_type == "agent.execution.requested.v1"
            await message.ack()

        consumer._persist_and_ack = fake_persist
        await consumer._on_message(sample_message)
        assert persist_called
        sample_message.ack.assert_awaited_once()


class TestDuplicateHandling:
    """Duplicate messages with same idempotency key must be ACKed not NACKed."""

    @pytest.mark.asyncio
    async def test_on_message_catches_integrity_error(self, mock_engine, mock_rabbitmq, sample_message):
        """When _persist_and_ack raises IntegrityError, consumer logs and continues."""
        from sqlalchemy.exc import IntegrityError

        consumer = MeteringInboxConsumerWorker(
            async_engine=mock_engine,
            rabbitmq_manager=mock_rabbitmq,
        )

        catch_called = False

        async def raise_integrity(message, model):
            nonlocal catch_called
            catch_called = True
            raise IntegrityError("duplicate key", None, None)

        consumer._persist_and_ack = raise_integrity
        with pytest.raises(IntegrityError):
            await consumer._on_message(sample_message)
        assert catch_called


class TestInvalidEnvelope:
    """Invalid messages must be rejected (NACK without requeue -> DLQ)."""

    @pytest.mark.asyncio
    async def test_rejects_invalid_message(self, mock_engine, mock_rabbitmq):
        """Message with missing required fields is rejected."""
        bad_payload = {"not_an_event": True}
        message = MagicMock()
        message.body = json.dumps(bad_payload).encode()
        message.routing_key = "unknown.key"
        message.correlation_id = None
        message.headers = {}
        message.message_id = str(uuid4())
        message.ack = AsyncMock()
        message.nack = AsyncMock()

        consumer = MeteringInboxConsumerWorker(
            async_engine=mock_engine,
            rabbitmq_manager=mock_rabbitmq,
        )

        reject_called = False

        async def raise_value_error(message, model):
            nonlocal reject_called
            reject_called = True
            raise ValueError("Missing event_type")

        consumer._persist_and_ack = raise_value_error
        consumer.reject = AsyncMock()
        await consumer._on_message(message)
        assert reject_called


class TestDBFailure:
    """Database failure during inbox persist must propagate for retry/backoff."""

    @pytest.mark.asyncio
    async def test_db_error_propagates(self, mock_engine, mock_rabbitmq, sample_message):
        consumer = MeteringInboxConsumerWorker(
            async_engine=mock_engine,
            rabbitmq_manager=mock_rabbitmq,
        )

        async def raise_db_error(message, model):
            raise RuntimeError("connection lost")

        consumer._persist_and_ack = raise_db_error
        with pytest.raises(RuntimeError, match="connection lost"):
            await consumer._on_message(sample_message)

    @pytest.mark.asyncio
    async def test_rabbit_message_to_inbox_with_missing_routing_key_defaults(self):
        """rabbit_message_to_inbox provides defaults for missing optional fields."""
        payload = {"event_type": "agent.execution.started.v1", "event_version": 1}
        message = MagicMock()
        message.body = json.dumps(payload).encode()
        message.routing_key = "agent.execution.started.v1"
        message.correlation_id = None
        message.headers = {}
        message.message_id = str(uuid4())

        model = rabbit_message_to_inbox(message)
        assert model.event_type == "agent.execution.started.v1"
        assert model.payload == {}


class TestBindingExactness:
    """Only quantifiable agent.execution events should be bound."""

    def test_bindings_contain_all_expected_keys(self):
        expected = {
            "agent.execution.requested.v1",
            "agent.execution.started.v1",
            "agent.execution.llm_completed.v1",
            "agent.execution.tool_completed.v1",
            "agent.execution.fallback_triggered.v1",
            "agent.execution.completed.v1",
            "agent.execution.failed.v1",
        }
        actual = set(METERING_INBOX_ROUTING_KEYS)
        assert actual == expected, f"Mismatch: extra={actual - expected}, missing={expected - actual}"


class TestRegistry:
    """register_metering_workers must wire the consumer and processor."""

    def test_registry_wires_consumer_and_processor(self):
        registry = MagicMock()
        engine = MagicMock()
        rabbitmq = MagicMock()
        register_metering_workers(
            registry=registry,
            engine=engine,
            rabbitmq_manager=rabbitmq,
        )
        assert registry.register.call_count == 3

    def test_registry_returns_early_without_engine_or_rabbitmq(self):
        registry = MagicMock()
        register_metering_workers(registry=registry)
        registry.register.assert_not_called()
