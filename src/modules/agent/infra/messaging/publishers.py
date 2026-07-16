"""Agent RabbitMQ publisher — publishes outbox events with publisher confirms."""
from __future__ import annotations

import logging

from aio_pika import DeliveryMode, Message

from modules.agent.infra.messaging.event_mappers import RabbitMQMessageEnvelope
from shared.infra.rabbitmq import RabbitMQManager

logger = logging.getLogger(__name__)

# Tool lifecycle events are currently internal notifications with no mandatory
# cross-module consumer in the MVP topology. Publishing them with RabbitMQ's
# mandatory flag enabled makes the broker return NO_ROUTE and causes the outbox
# dispatcher to retry forever. Execution events remain mandatory because they
# feed metering/observability and a missing binding should fail loudly.
OPTIONAL_UNROUTED_ROUTING_KEYS: frozenset[str] = frozenset(
    {
        "agent.tool.created.v1",
        "agent.tool.updated.v1",
        "agent.tool.status_changed.v1",
    }
)


class AgentRabbitMQPublisher:
    def __init__(self, rabbitmq_manager: RabbitMQManager) -> None:
        self._manager = rabbitmq_manager

    async def publish(self, envelope: RabbitMQMessageEnvelope) -> None:
        body = envelope.body.encode()
        message = Message(
            body=body,
            delivery_mode=DeliveryMode.PERSISTENT,
            correlation_id=envelope.correlation_id,
            content_type="application/json",
            headers=envelope.headers or {},
            message_id=envelope.message_id,
        )
        mandatory = envelope.routing_key not in OPTIONAL_UNROUTED_ROUTING_KEYS
        confirm = await self._manager.exchange.publish(
            message=message,
            routing_key=envelope.routing_key,
            mandatory=mandatory,
        )
        if confirm is False:
            raise RuntimeError(
                "RabbitMQ did not confirm publication "
                f"routing_key={envelope.routing_key} message_id={envelope.message_id}"
            )
        logger.info(
            "Published Agent event routing_key=%s message_id=%s correlation_id=%s mandatory=%s",
            envelope.routing_key,
            envelope.message_id,
            envelope.correlation_id,
            mandatory,
        )
