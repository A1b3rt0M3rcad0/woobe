from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from modules.core.infra.messaging.event_mappers import rabbit_message_to_inbox
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.inbox_consumer_base import BaseInboxConsumer, InboxRecord

logger = logging.getLogger(__name__)

CORE_INBOX_QUEUE: str = "core.inbox"
CORE_INBOX_ROUTING_KEYS: list[str] = ["core.#"]


class CoreInboxConsumerWorker(BaseInboxConsumer):
    def __init__(
        self,
        async_engine: AsyncEngine,
        rabbitmq_manager: RabbitMQManager,
        queue_name: str = CORE_INBOX_QUEUE,
        routing_keys: list[str] | None = None,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(async_engine)
        self._rabbitmq_manager = rabbitmq_manager
        self._queue_name = queue_name
        self._routing_keys = routing_keys or list(CORE_INBOX_ROUTING_KEYS)
        self._worker_id = worker_id or f"core-inbox-consumer-{os.getpid()}"

    async def consume(self) -> None:
        await self._rabbitmq_manager.consume(
            queue_name=self._queue_name,
            routing_keys=self._routing_keys,
            callback=self._on_message,
        )

    async def _on_message(self, message: Any) -> None:
        try:
            inbox_model = rabbit_message_to_inbox(message)
            await self._persist_and_ack(message, inbox_model)
        except (ValueError, KeyError) as exc:
            logger.warning("Invalid message rejected: %s", str(exc))
            await self.reject(message, str(exc))

    async def _persist_and_ack(self, message: Any, inbox_model: Any) -> None:
        async with AsyncSession(self._async_engine) as session:
            async with session.begin():
                session.add(inbox_model)
                try:
                    await session.flush()
                except IntegrityError:
                    logger.warning("Duplicate inbox message: %s", inbox_model.event_type)
                    await session.rollback()
                    await self.acknowledge(message)
                    return
        await self.acknowledge(message)

    async def persist_inbox(self, record: InboxRecord) -> None:
        pass

    async def acknowledge(self, message: Any) -> None:
        if hasattr(message, "ack"):
            await message.ack()

    async def reject(self, message: Any, error: str) -> None:
        if hasattr(message, "reject"):
            await message.reject(requeue=False)
