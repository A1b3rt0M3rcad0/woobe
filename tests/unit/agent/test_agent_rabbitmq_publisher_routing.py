from __future__ import annotations

import pytest

from modules.agent.infra.messaging.event_mappers import RabbitMQMessageEnvelope
from modules.agent.infra.messaging.publishers import AgentRabbitMQPublisher


class FakeExchange:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def publish(self, **kwargs):
        self.calls.append(kwargs)
        return True


class FakeRabbitMQManager:
    def __init__(self) -> None:
        self.exchange = FakeExchange()


@pytest.mark.asyncio
async def test_tool_lifecycle_events_are_published_as_optional_unrouted() -> None:
    manager = FakeRabbitMQManager()
    publisher = AgentRabbitMQPublisher(manager)  # type: ignore[arg-type]

    await publisher.publish(
        RabbitMQMessageEnvelope(
            routing_key="agent.tool.created.v1",
            body="{}",
            correlation_id="correlation-id",
            message_id="message-id",
        )
    )

    assert manager.exchange.calls[0]["routing_key"] == "agent.tool.created.v1"
    assert manager.exchange.calls[0]["mandatory"] is False


@pytest.mark.asyncio
async def test_execution_events_remain_mandatory() -> None:
    manager = FakeRabbitMQManager()
    publisher = AgentRabbitMQPublisher(manager)  # type: ignore[arg-type]

    await publisher.publish(
        RabbitMQMessageEnvelope(
            routing_key="agent.execution.completed.v1",
            body="{}",
            correlation_id="correlation-id",
            message_id="message-id",
        )
    )

    assert manager.exchange.calls[0]["routing_key"] == "agent.execution.completed.v1"
    assert manager.exchange.calls[0]["mandatory"] is True
