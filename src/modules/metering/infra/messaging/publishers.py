from __future__ import annotations

import logging

from aio_pika import DeliveryMode, Message

from modules.metering.infra.messaging.event_mappers import RabbitMQMessageEnvelope
from shared.infra.rabbitmq import RabbitMQManager

logger = logging.getLogger(__name__)


class MeteringRabbitMQPublisher:
    def __init__(self, rabbitmq_manager: RabbitMQManager) -> None:
        self._manager = rabbitmq_manager

    async def publish(self, envelope: RabbitMQMessageEnvelope) -> None:
        message = Message(
            body=envelope.body.encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            correlation_id=envelope.correlation_id,
            content_type="application/json",
            headers=envelope.headers or {},
        )
        await self._manager.exchange.publish(
            message=message,
            routing_key=envelope.routing_key,
        )
        logger.debug(
            "Published event to %s with correlation_id=%s",
            envelope.routing_key,
            envelope.correlation_id,
        )
