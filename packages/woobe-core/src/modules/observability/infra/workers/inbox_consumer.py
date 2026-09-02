from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from modules.observability.infra.database.repositories import ObservabilityInboxStore
from modules.observability.infra.database.unit_of_work import ObservabilityUnitOfWork
from modules.observability.infra.messaging.event_mappers import rabbit_message_to_inbox
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.inbox_consumer_base import BaseInboxConsumer, InboxRecord

logger = logging.getLogger(__name__)

OBSERVABILITY_INBOX_QUEUE: str = "observability.inbox"
OBSERVABILITY_INBOX_ROUTING_KEYS: list[str] = [
    "agent.execution.requested.v1",
    "agent.execution.started.v1",
    "agent.execution.llm_completed.v1",
    "agent.execution.tool_completed.v1",
    "agent.execution.fallback_triggered.v1",
    "agent.execution.completed.v1",
    "agent.execution.failed.v1",
]


class ObservabilityInboxConsumerWorker(BaseInboxConsumer):
    def __init__(
        self,
        async_engine: AsyncEngine,
        rabbitmq_manager: RabbitMQManager,
        queue_name: str = OBSERVABILITY_INBOX_QUEUE,
        routing_keys: list[str] | None = None,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(async_engine)
        self._rabbitmq_manager = rabbitmq_manager
        self._queue_name = queue_name
        self._routing_keys = routing_keys or list(OBSERVABILITY_INBOX_ROUTING_KEYS)
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
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("Invalid observability message rejected: %s", str(exc))
            await self.reject(message, str(exc))
        except Exception as exc:
            logger.exception("Failed to persist observability Inbox message: %s", exc)
            if hasattr(message, "nack"):
                await message.nack(requeue=True)
            else:
                raise

    async def _persist_and_ack(self, message: Any, inbox_model: Any) -> None:
        event_type = getattr(inbox_model, "event_type", "unknown")
        message_id = getattr(inbox_model, "message_id", "unknown")
        idempotency_key = getattr(inbox_model, "idempotency_key", "unknown")
        duplicate = False
        try:
            async with ObservabilityUnitOfWork(self._async_engine) as uow:
                await ObservabilityInboxStore(uow).save_received(inbox_model)
        except IntegrityError:
            duplicate = True

        if duplicate:
            logger.info(
                "Duplicate observability message acknowledged idempotency_key=%s",
                idempotency_key,
            )
        else:
            logger.info(
                "Persisted Observability Inbox event_type=%s message_id=%s",
                event_type,
                message_id,
            )
        await self.acknowledge(message)

    async def persist_inbox(self, record: InboxRecord) -> None:
        from modules.observability.infra.database.models import InboxEventModel

        model = InboxEventModel()
        model.event_type = record.event_type
        model.event_version = record.event_version
        model.payload = record.payload
        model.correlation_id = record.correlation_id
        model.causation_id = record.causation_id
        model.outbox_origin_id = record.outbox_origin_id
        model.aggregate_type = record.aggregate_type
        model.status = "received"
        model.attempts = 0
        async with ObservabilityUnitOfWork(self._async_engine) as uow:
            await ObservabilityInboxStore(uow).save_received(model)

    async def acknowledge(self, message: Any) -> None:
        if hasattr(message, "ack"):
            await message.ack()

    async def reject(self, message: Any, error: str) -> None:
        logger.warning("Rejecting observability message: %s", error)
        if hasattr(message, "nack"):
            await message.nack(requeue=False)
        elif hasattr(message, "reject"):
            await message.reject(requeue=False)
