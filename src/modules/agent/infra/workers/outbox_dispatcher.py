"""Agent outbox dispatcher worker — claims pending outbox events and publishes to RabbitMQ."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from modules.agent.infra.database.models import AgentOutboxEventModel
from modules.agent.infra.database.repositories import (
    AGENT_DEFAULT_BATCH_SIZE,
    SQLAlchemyAgentOutboxRepository,
)
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
        self._session: AsyncSession | None = None
        self._repo: SQLAlchemyAgentOutboxRepository | None = None
        self._event_map: dict[UUID, AgentOutboxEventModel] = {}

    async def run(self) -> None:
        async with AsyncSession(self._async_engine) as session:
            async with session.begin():
                self._session = session
                self._repo = SQLAlchemyAgentOutboxRepository(session)
                self._event_map = {}
                await super().run()
        self._session = None
        self._repo = None
        self._event_map = {}

    async def claim_pending(self, limit: int) -> list[OutboxRecord]:
        assert self._repo is not None
        events = await self._repo.claim_batch(
            batch_size=limit, locked_by=self._worker_id
        )
        records: list[OutboxRecord] = []
        for event in events:
            record = OutboxRecord(
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
            records.append(record)
            self._event_map[event.id] = event
        return records

    async def publish(self, record: OutboxRecord) -> None:
        event = self._event_map[record.id]
        envelope = outbox_to_rabbit_message(event)
        await self._publisher.publish(envelope)

    async def mark_published(self, record: OutboxRecord) -> None:
        assert self._repo is not None
        await self._repo.mark_published(record.id)

    async def mark_dead(self, record: OutboxRecord) -> None:
        assert self._repo is not None
        await self._repo.mark_dead(record.id, record.error or "max attempts exceeded")

    async def mark_retryable(self, record: OutboxRecord) -> None:
        assert self._repo is not None
        backoff = timedelta(seconds=RETRY_BACKOFF_BASE_SECONDS * (record.attempts + 1))
        available_at = datetime.now(timezone.utc) + backoff
        await self._repo.mark_retryable(
            record.id, record.error or "transient failure", available_at
        )
