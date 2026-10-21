"""Agent outbox dispatcher worker — claims pending outbox events and publishes to RabbitMQ."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.background_boundary import (
    AGENT_DEFAULT_BATCH_SIZE,
    AgentOutboxEventModel,
    SQLAlchemyAgentOutboxRepository,
    AgentUnitOfWork,
    RabbitMQMessageEnvelope,
    outbox_to_rabbit_message,
)
from woobe_workers.runtime.outbox_dispatcher_base import BaseOutboxDispatcher, OutboxRecord

logger = logging.getLogger(__name__)

RETRY_BACKOFF_BASE_SECONDS: int = 30


class AgentOutboxPublisherProtocol(Protocol):
    async def publish(self, envelope: RabbitMQMessageEnvelope) -> None: ...


class AgentOutboxDispatcherWorker(BaseOutboxDispatcher):
    BATCH_SIZE: int = AGENT_DEFAULT_BATCH_SIZE
    MAX_ATTEMPTS: int = 5

    def __init__(
        self,
        async_engine: AsyncEngine,
        publisher: AgentOutboxPublisherProtocol,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(async_engine)
        self._publisher = publisher
        self._worker_id = worker_id or f"outbox-dispatcher-{os.getpid()}"
        self._envelope_map: dict[UUID, RabbitMQMessageEnvelope] = {}

    async def run(self) -> None:
        records = await self.claim_pending(limit=self.BATCH_SIZE)
        if not records:
            return

        published: list[OutboxRecord] = []
        retryable: list[OutboxRecord] = []
        dead: list[OutboxRecord] = []

        for record in records:
            try:
                await self.publish(record)
                published.append(record)
            except Exception as exc:
                logger.exception(
                    "Failed to publish Agent outbox record %s: %s",
                    record.id,
                    exc,
                )
                record.error = str(exc)
                if record.attempts + 1 >= self.MAX_ATTEMPTS:
                    dead.append(record)
                else:
                    retryable.append(record)

        async with AgentUnitOfWork(self._async_engine) as uow:
            repo = SQLAlchemyAgentOutboxRepository(uow)
            for record in published:
                await repo.mark_published(record.id)
            for record in retryable:
                backoff = timedelta(
                    seconds=RETRY_BACKOFF_BASE_SECONDS
                    * (record.attempts + 1)
                )
                await repo.mark_retryable(
                    record.id,
                    record.error or "transient failure",
                    datetime.now(timezone.utc) + backoff,
                )
            for record in dead:
                await repo.mark_dead(
                    record.id,
                    record.error or "max attempts exceeded",
                )

        self._envelope_map = {}

    async def claim_pending(self, limit: int) -> list[OutboxRecord]:
        envelope_map: dict[UUID, RabbitMQMessageEnvelope] = {}
        records: list[OutboxRecord] = []

        async with AgentUnitOfWork(self._async_engine) as uow:
            repo = SQLAlchemyAgentOutboxRepository(uow)
            events = await repo.claim_batch(
                batch_size=limit,
                locked_by=self._worker_id,
            )
            for event in events:
                records.append(self._record(event))
                envelope_map[event.id] = outbox_to_rabbit_message(event)

        self._envelope_map = envelope_map
        return records

    @staticmethod
    def _record(event: AgentOutboxEventModel) -> OutboxRecord:
        return OutboxRecord(
            id=event.id,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            event_type=event.event_type,
            event_version=event.event_version,
            payload=event.payload or {},
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            attempts=event.attempts,
            error=event.error,
        )

    async def publish(self, record: OutboxRecord) -> None:
        envelope = self._envelope_map.get(record.id)
        if envelope is None:
            raise ValueError(f"Outbox record {record.id} not in claimed batch")
        await self._publisher.publish(envelope)

    async def mark_published(self, record: OutboxRecord) -> None:
        async with AgentUnitOfWork(self._async_engine) as uow:
            await SQLAlchemyAgentOutboxRepository(uow).mark_published(record.id)

    async def mark_dead(self, record: OutboxRecord) -> None:
        async with AgentUnitOfWork(self._async_engine) as uow:
            await SQLAlchemyAgentOutboxRepository(uow).mark_dead(
                record.id,
                record.error or "max attempts exceeded",
            )

    async def mark_retryable(self, record: OutboxRecord) -> None:
        backoff = timedelta(
            seconds=RETRY_BACKOFF_BASE_SECONDS * (record.attempts + 1)
        )
        async with AgentUnitOfWork(self._async_engine) as uow:
            await SQLAlchemyAgentOutboxRepository(uow).mark_retryable(
                record.id,
                record.error or "transient failure",
                datetime.now(timezone.utc) + backoff,
            )
