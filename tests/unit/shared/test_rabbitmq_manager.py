from __future__ import annotations

from typing import Any

import aio_pika
import pytest

from shared.infra.rabbitmq import RabbitMQManager


@pytest.mark.asyncio
async def test_connect_enables_publisher_confirms_on_channel(monkeypatch) -> None:
    calls: dict[str, Any] = {}

    class FakeExchange:
        pass

    class FakeChannel:
        is_closed = False

        async def declare_exchange(self, **kwargs):
            calls.setdefault("exchanges", []).append(kwargs)
            return FakeExchange()

    class FakeConnection:
        is_closed = False

        async def channel(self, **kwargs):
            calls["channel"] = kwargs
            return FakeChannel()

        async def close(self):
            self.is_closed = True

    async def fake_connect_robust(url: str):
        calls["url"] = url
        return FakeConnection()

    monkeypatch.setattr(aio_pika, "connect_robust", fake_connect_robust)

    manager = RabbitMQManager(
        url="amqp://guest:guest@rabbitmq:5672/",
        exchange_name="projectrai.events",
    )
    await manager.connect()

    assert manager.is_connected is True
    assert calls["channel"] == {
        "publisher_confirms": True,
        "on_return_raises": True,
    }
    assert [item["name"] for item in calls["exchanges"]] == [
        "projectrai.events",
        "projectrai.events.dlx",
    ]


@pytest.mark.asyncio
async def test_connect_failure_leaves_manager_disconnected(monkeypatch) -> None:
    async def fake_connect_robust(_url: str):
        raise ConnectionError("broker unavailable")

    monkeypatch.setattr(aio_pika, "connect_robust", fake_connect_robust)

    manager = RabbitMQManager(
        url="amqp://guest:guest@rabbitmq:5672/",
        exchange_name="projectrai.events",
    )

    with pytest.raises(ConnectionError, match="broker unavailable"):
        await manager.connect()

    assert manager.is_connected is False
    with pytest.raises(RuntimeError, match="not connected"):
        _ = manager.exchange
