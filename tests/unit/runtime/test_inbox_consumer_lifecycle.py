from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.infra.rabbitmq import RabbitMQManager
from woobe_workers.consumers.metering.inbox_consumer import MeteringInboxConsumerWorker
from woobe_workers.consumers.observability.inbox_consumer import (
    ObservabilityInboxConsumerWorker,
)
from woobe_workers.runtime.runner import WorkerRunner


@pytest.mark.anyio
@pytest.mark.parametrize(
    "consumer_type", [MeteringInboxConsumerWorker, ObservabilityInboxConsumerWorker]
)
async def test_registered_inbox_consumer_stays_running_until_shutdown(
    consumer_type,
) -> None:
    manager = MagicMock(spec=RabbitMQManager)
    registered = asyncio.Event()

    async def register(**_kwargs) -> None:
        registered.set()

    manager.consume = AsyncMock(side_effect=register)
    consumer = consumer_type(async_engine=MagicMock(), rabbitmq_manager=manager)
    runner = WorkerRunner([consumer])
    await runner.start()
    try:
        await asyncio.wait_for(registered.wait(), timeout=1)
        await asyncio.sleep(0)
        assert runner.get_health()[0].is_running
        assert runner.get_health()[0].error is None
        manager.consume.assert_awaited_once()
    finally:
        await asyncio.wait_for(runner.stop(), timeout=1)
    assert not runner.get_health()[0].is_running


@pytest.mark.anyio
async def test_subscription_failure_remains_unhealthy() -> None:
    manager = MagicMock(spec=RabbitMQManager)
    manager.consume = AsyncMock(side_effect=RuntimeError("subscription unavailable"))
    consumer = MeteringInboxConsumerWorker(
        async_engine=MagicMock(), rabbitmq_manager=manager
    )
    runner = WorkerRunner([consumer])
    await runner.start()
    try:
        await asyncio.sleep(0)
        assert not runner.get_health()[0].is_running
        assert runner.get_health()[0].error == "RuntimeError"
    finally:
        await asyncio.wait_for(runner.stop(), timeout=1)
