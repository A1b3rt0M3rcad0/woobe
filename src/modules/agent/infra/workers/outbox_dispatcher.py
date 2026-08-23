"""Agent outbox dispatcher worker — claims pending outbox events and publishes to RabbitMQ."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.infra.database.models import AgentOutboxEventModel
from modules.agent.infra.database.repositories import (
    AGENT_DEFAULT_BATCH_SIZE,
    AGENT_OUTBOX_LOCK_TIMEOUT_SECONDS,
    SQLAlchemyAgentOutboxRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.messaging.event_mappers import (
    RabbitMQMessageEnvelope,
    outbox_to_rabbit_message,
)
from shared.workers.outbox_dispatcher_base import BaseOutboxDispatcher, OutboxRecord

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
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(
            seconds=AGENT_OUTBOX_LOCK_TIMEOUT_SECONDS
        )
        envelope_map: dict[UUID, RabbitMQMessageEnvelope] = {}
        records: list[OutboxRecord] = []

        async with AgentUnitOfWork(self._async_engine) as uow:
            result = await uow.session.execute(
                select(AgentOutboxEventModel)
                .where(
                    AgentOutboxEventModel.status.in_(
                        ["pending", "retryable", "publishing"]
                    ),
                    AgentOutboxEventModel.available_at <= func.now(),
                    or_(
                        AgentOutboxEventModel.locked_at.is_(None),
                        AgentOutboxEventModel.locked_at < stale_before,
                    ),
                )
                .order_by(AgentOutboxEventModel.created_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            events = list(result.scalars().all())
            for event in events:
                event.status = "publishing"
                event.locked_at = now
                event.locked_by = self._worker_id
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
