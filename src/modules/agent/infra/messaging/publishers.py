"""Agent RabbitMQ publisher — publishes outbox events with publisher confirms."""
from __future__ import annotations

import logging

from aio_pika import DeliveryMode, Message

from modules.agent.infra.messaging.event_mappers import RabbitMQMessageEnvelope
from shared.infra.rabbitmq import RabbitMQManager

logger = logging.getLogger(__name__)


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
        confirm = await self._manager.exchange.publish(
            message=message,
            routing_key=envelope.routing_key,
        )
        if confirm is False:
            raise RuntimeError(
                "RabbitMQ did not confirm publication "
                f"routing_key={envelope.routing_key} message_id={envelope.message_id}"
            )
        logger.info(
            "Published Agent event routing_key=%s message_id=%s correlation_id=%s",
            envelope.routing_key,
            envelope.message_id,
            envelope.correlation_id,
        )
