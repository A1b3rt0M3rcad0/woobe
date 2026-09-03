"""Agent inbox consumer worker — consumes messages from RabbitMQ and persists to inbox."""
from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.background_boundary import SQLAlchemyAgentInboxRepository
from modules.agent.background_boundary import AgentUnitOfWork
from modules.agent.background_boundary import rabbit_message_to_inbox
from shared.infra.rabbitmq import RabbitMQManager
from woobe_workers.runtime.inbox_consumer_base import BaseInboxConsumer, InboxRecord

logger = logging.getLogger(__name__)

AGENT_INBOX_QUEUE: str = "agent.inbox"
AGENT_INBOX_ROUTING_KEYS: list[str] = []


class AgentInboxConsumerWorker(BaseInboxConsumer):
    def __init__(
        self,
        async_engine: AsyncEngine,
        rabbitmq_manager: RabbitMQManager,
        queue_name: str = AGENT_INBOX_QUEUE,
        routing_keys: list[str] | None = None,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(async_engine)
        self._rabbitmq_manager = rabbitmq_manager
        self._queue_name = queue_name
        self._routing_keys = routing_keys or list(AGENT_INBOX_ROUTING_KEYS)
        self._worker_id = worker_id or f"inbox-consumer-{os.getpid()}"

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
            logger.warning(
                "Invalid message rejected: %s",
                str(exc),
            )
            await self.reject(message, str(exc))

    async def _persist_and_ack(self, message: Any, inbox_model: Any) -> None:
        try:
            async with AgentUnitOfWork(self._async_engine) as uow:
                repo = SQLAlchemyAgentInboxRepository(uow)
                await repo.save_received(inbox_model)
        except IntegrityError:
            logger.debug(
                "Duplicate message acknowledged (idempotency_key=%s)",
                getattr(inbox_model, "idempotency_key", "unknown"),
            )
        await self.acknowledge(message)

    async def persist_inbox(self, record: InboxRecord) -> None:
        async with AgentUnitOfWork(self._async_engine) as uow:
            repo = SQLAlchemyAgentInboxRepository(uow)
            from modules.agent.background_boundary import AgentInboxEventModel

            model = AgentInboxEventModel()
            model.event_type = record.event_type
            model.event_version = record.event_version
            model.payload = record.payload
            model.correlation_id = record.correlation_id
            model.causation_id = record.causation_id
            model.status = "received"
            model.attempts = 0
            await repo.save_received(model)

    async def acknowledge(self, message: Any) -> None:
        if hasattr(message, "ack"):
            await message.ack()

    async def reject(self, message: Any, error: str) -> None:
        logger.warning("Rejecting message: %s", error)
        if hasattr(message, "nack"):
            await message.nack(requeue=False)
        elif hasattr(message, "reject"):
            await message.reject(requeue=False)
