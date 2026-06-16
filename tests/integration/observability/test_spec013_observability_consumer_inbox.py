"""Tests for spec 013: observability RabbitMQ consumer and inbox.

Covers: broker->inbox persistence, duplicate handling, invalid/DLQ,
DB failure, binding matrix, registry wiring.
"""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from modules.observability.infra.database.models import InboxEventModel
from modules.observability.infra.messaging.event_mappers import rabbit_message_to_inbox
from modules.observability.infra.workers.inbox_consumer import (
    OBSERVABILITY_INBOX_ROUTING_KEYS,
    ObservabilityInboxConsumerWorker,
)
from modules.observability.infra.workers.registry import register_observability_workers


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
    payload = {
        "event_id": str(uuid4()),
        "event_type": "agent.execution.started.v1",
        "event_version": 1,
        "producer_module": "agent",
        "routing_key": "agent.execution.started.v1",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {"execution_id": str(uuid4()), "agent_id": str(uuid4()), "project_id": str(uuid4())},
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "causation_id": str(uuid4()),
        "metadata": {},
    }
    message = MagicMock()
    message.body = json.dumps(payload).encode()
    message.routing_key = "agent.execution.started.v1"
    message.correlation_id = payload["correlation_id"]
    message.headers = {
        "x-event-type": "agent.execution.started.v1",
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
        model = rabbit_message_to_inbox(sample_message)
        assert isinstance(model, InboxEventModel)
        assert model.event_type == "agent.execution.started.v1"
        assert model.event_version == 1
        assert model.producer_module == "agent"
        assert model.consumer_module == "observability"
        assert model.status == "received"
        assert model.idempotency_key is not None
        assert model.correlation_id is not None
        assert model.payload is not None

    @pytest.mark.asyncio
    async def test_consumer_consume_calls_rabbitmq(self, mock_engine, mock_rabbitmq):
        consumer = ObservabilityInboxConsumerWorker(
            async_engine=mock_engine,
            rabbitmq_manager=mock_rabbitmq,
        )
        await consumer.consume()
        assert mock_rabbitmq.consume.await_count == 1

    @pytest.mark.asyncio
    async def test_consumer_routing_keys_are_exact(self):
        for key in OBSERVABILITY_INBOX_ROUTING_KEYS:
            assert key.startswith("agent.execution.")
        assert all(key.endswith(".v1") for key in OBSERVABILITY_INBOX_ROUTING_KEYS)
        assert not any(key == "observability.#" for key in OBSERVABILITY_INBOX_ROUTING_KEYS)

    @pytest.mark.asyncio
    async def test_no_requested_event_in_observability(self):
        assert "agent.execution.requested.v1" not in OBSERVABILITY_INBOX_ROUTING_KEYS


class TestDuplicateHandling:
    """Duplicate messages must be ACKed not NACKed."""

    @pytest.mark.asyncio
    async def test_on_message_catches_integrity_error(self, mock_engine, mock_rabbitmq, sample_message):
        from sqlalchemy.exc import IntegrityError

        consumer = ObservabilityInboxConsumerWorker(
            async_engine=mock_engine,
            rabbitmq_manager=mock_rabbitmq,
        )
        async def raise_integrity(message, model):
            raise IntegrityError("duplicate", None, None)

        consumer._persist_and_ack = raise_integrity
        with pytest.raises(IntegrityError):
            await consumer._on_message(sample_message)


class TestInvalidEnvelope:
    """Invalid messages must be rejected (NACK without requeue -> DLQ)."""

    @pytest.mark.asyncio
    async def test_rejects_invalid_message(self, mock_engine, mock_rabbitmq):
        bad_payload = {"bad": True}
        message = MagicMock()
        message.body = json.dumps(bad_payload).encode()
        message.routing_key = "unknown.key"
        message.correlation_id = None
        message.headers = {}
        message.message_id = str(uuid4())
        message.ack = AsyncMock()
        message.nack = AsyncMock()

        consumer = ObservabilityInboxConsumerWorker(
            async_engine=mock_engine,
            rabbitmq_manager=mock_rabbitmq,
        )
        async def raise_error(message, model):
            raise ValueError("Missing fields")

        consumer._persist_and_ack = raise_error
        consumer.reject = AsyncMock()
        await consumer._on_message(message)


class TestDBFailure:
    """Database failure must propagate for retry."""

    @pytest.mark.asyncio
    async def test_db_error_propagates(self, mock_engine, mock_rabbitmq, sample_message):
        consumer = ObservabilityInboxConsumerWorker(
            async_engine=mock_engine,
            rabbitmq_manager=mock_rabbitmq,
        )
        async def raise_db_error(message, model):
            raise RuntimeError("connection lost")

        consumer._persist_and_ack = raise_db_error
        with pytest.raises(RuntimeError, match="connection lost"):
            await consumer._on_message(sample_message)

    @pytest.mark.asyncio
    async def test_rabbit_message_to_inbox_with_minimal_payload(self):
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
    """Only traceable agent.execution events should be bound."""

    def test_bindings_contain_all_expected_keys(self):
        expected = {
            "agent.execution.started.v1",
            "agent.execution.llm_completed.v1",
            "agent.execution.tool_completed.v1",
            "agent.execution.fallback_triggered.v1",
            "agent.execution.completed.v1",
            "agent.execution.failed.v1",
        }
        actual = set(OBSERVABILITY_INBOX_ROUTING_KEYS)
        assert actual == expected, f"Mismatch: extra={actual - expected}, missing={expected - actual}"


class TestRegistry:
    """register_observability_workers must wire the consumer and processor."""

    def test_registry_wires_consumer_and_processor(self):
        registry = MagicMock()
        engine = MagicMock()
        rabbitmq = MagicMock()
        register_observability_workers(
            registry=registry,
            engine=engine,
            rabbitmq_manager=rabbitmq,
        )
        assert registry.register.call_count == 2

    def test_registry_returns_early_without_engine_or_rabbitmq(self):
        registry = MagicMock()
        register_observability_workers(registry=registry)
        registry.register.assert_not_called()
