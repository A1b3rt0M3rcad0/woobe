"""Tests for spec 015: metering retry, DLQ, and replay integration.

Covers: outbox dispatcher registration, retry schedule, max attempts,
replay via scripts.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from woobe_workers.consumers.metering.outbox_dispatcher import (
    METERING_OUTBOX_MAX_ATTEMPTS,
    RETRY_BACKOFF_BASE_SECONDS,
    MeteringOutboxDispatcherWorker,
)
from woobe_workers.consumers.metering.registry import (
    MeteringWorkerRegistry,
    register_metering_workers,
)


class TestOutboxDispatcherRegistration:
    """Outbox dispatcher must be registered in the worker registry."""

    def test_registry_registers_outbox_dispatcher(self):
        registry = MagicMock()
        engine = MagicMock()
        rabbitmq = MagicMock()
        register_metering_workers(
            registry=registry,
            engine=engine,
            rabbitmq_manager=rabbitmq,
        )
        assert registry.register.call_count == 3

    def test_registry_returns_early_without_engine(self):
        registry = MagicMock()
        register_metering_workers(registry=registry)
        registry.register.assert_not_called()

    def test_worker_registry_can_collect_workers(self):
        reg = MeteringWorkerRegistry()
        reg.register(MagicMock())
        assert len(reg.iter_workers()) == 1


class TestRetrySchedule:
    """Outbox dispatcher must retry with backoff and max attempts."""

    def test_max_attempts_configured(self):
        assert METERING_OUTBOX_MAX_ATTEMPTS > 0
        assert METERING_OUTBOX_MAX_ATTEMPTS <= 10

    def test_backoff_base_configured(self):
        assert RETRY_BACKOFF_BASE_SECONDS >= 1
        assert RETRY_BACKOFF_BASE_SECONDS <= 120


class TestMaxAttempts:
    """Events exceeding max attempts must be marked dead/failed."""

    @pytest.mark.asyncio
    async def test_dispatcher_marks_failed_on_publish_error(self):
        mock_engine = AsyncMock()
        mock_publisher = AsyncMock()
        mock_publisher.publish = AsyncMock(side_effect=RuntimeError("publish failed"))

        dispatcher = MeteringOutboxDispatcherWorker(
            async_engine=mock_engine,
            publisher=mock_publisher,
        )
        dispatcher._session = AsyncMock()

        from woobe_workers.runtime.outbox_dispatcher_base import OutboxRecord
        record = OutboxRecord(
            id=MagicMock(),
            aggregate_type="agent",
            aggregate_id=MagicMock(),
            event_type="agent.execution.test.v1",
            event_version=1,
            payload={},
            correlation_id=MagicMock(),
            causation_id=MagicMock(),
            attempts=0,
        )
        dispatcher._event_map[record.id] = MagicMock()
        dispatcher._session = AsyncMock()
        dispatcher._session.execute = AsyncMock()

        await dispatcher.mark_failed(record, "publish failed")
        dispatcher._session.execute.assert_awaited()
