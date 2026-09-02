"""Identity inbox consumer — persists delivery atomically before acknowledging RabbitMQ."""

from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.infra.messaging.event_mappers import rabbit_message_to_inbox
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.inbox_consumer_base import BaseInboxConsumer, InboxRecord

logger = logging.getLogger(__name__)

IDENTITY_INBOX_QUEUE: str = "identity.inbox"
IDENTITY_INBOX_ROUTING_KEYS: list[str] = ["identity.#"]


class IdentityInboxConsumerWorker(BaseInboxConsumer):
    def __init__(
        self,
        async_engine: AsyncEngine,
        rabbitmq_manager: RabbitMQManager,
        queue_name: str = IDENTITY_INBOX_QUEUE,
        routing_keys: list[str] | None = None,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(async_engine)
        self._rabbitmq_manager = rabbitmq_manager
        self._queue_name = queue_name
        self._routing_keys = routing_keys or list(IDENTITY_INBOX_ROUTING_KEYS)
        self._worker_id = worker_id or f"identity-inbox-consumer-{os.getpid()}"

    async def consume(self) -> None:
        await self._rabbitmq_manager.consume(
            queue_name=self._queue_name,
            routing_keys=self._routing_keys,
            callback=self._on_message,
        )

    async def _on_message(self, message: Any) -> None:
        try:
            inbox_model = rabbit_message_to_inbox(message)
        except (ValueError, KeyError) as exc:
            logger.warning("Invalid message rejected: %s", str(exc))
            await self.reject(message, str(exc))
            return

        try:
            async with IdentityUnitOfWork(self._async_engine) as uow:
                uow.session.add(inbox_model)
                await uow.session.flush()
        except IntegrityError:
            logger.info("Duplicate Identity inbox message: %s", inbox_model.event_type)

        await self.acknowledge(message)

    async def persist_inbox(self, record: InboxRecord) -> None:
        del record

    async def acknowledge(self, message: Any) -> None:
        if hasattr(message, "ack"):
            await message.ack()

    async def reject(self, message: Any, error: str) -> None:
        del error
        if hasattr(message, "reject"):
            await message.reject(requeue=False)
