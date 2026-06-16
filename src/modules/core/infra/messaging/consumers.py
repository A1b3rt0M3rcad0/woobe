from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

from shared.infra.rabbitmq import RabbitMQManager

logger = logging.getLogger(__name__)

AsyncMessageCallback = Callable[[Any], Coroutine[Any, Any, None]]


class CoreRabbitMQConsumer:
    def __init__(self, rabbitmq_manager: RabbitMQManager) -> None:
        self._manager = rabbitmq_manager

    async def consume(
        self,
        queue_name: str,
        routing_keys: list[str],
        callback: AsyncMessageCallback,
    ) -> None:
        await self._manager.consume(
            queue_name=queue_name,
            routing_keys=routing_keys,
            callback=callback,
        )
        logger.info(
            "Consumer started for queue=%s with routing_keys=%s",
            queue_name,
            routing_keys,
        )
