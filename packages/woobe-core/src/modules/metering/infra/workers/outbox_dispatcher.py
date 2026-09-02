from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from modules.metering.infra.database.models import OutboxEventModel
from modules.metering.infra.database.unit_of_work import MeteringUnitOfWork
from modules.metering.infra.messaging.event_mappers import (
    RabbitMQMessageEnvelope,
    outbox_to_rabbit_message,
)
from shared.workers.outbox_dispatcher_base import BaseOutboxDispatcher, OutboxRecord

logger = logging.getLogger(__name__)

METERING_OUTBOX_BATCH_SIZE: int = 50
METERING_OUTBOX_MAX_ATTEMPTS: int = 5
RETRY_BACKOFF_BASE_SECONDS: int = 30


class MeteringOutboxPublisherProtocol(Protocol):
    async def publish(self, envelope: RabbitMQMessageEnvelope) -> None: ...


class MeteringOutboxDispatcherWorker(BaseOutboxDispatcher):
    BATCH_SIZE: int = METERING_OUTBOX_BATCH_SIZE
    MAX_ATTEMPTS: int = METERING_OUTBOX_MAX_ATTEMPTS

    def __init__(
        self,
        async_engine: AsyncEngine,
        publisher: MeteringOutboxPublisherProtocol,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(async_engine)
        self._publisher = publisher
        self._worker_id = worker_id or f"metering-outbox-dispatcher-{os.getpid()}"
        self._uow: MeteringUnitOfWork | None = None
        self._event_map: dict[UUID, OutboxEventModel] = {}

    async def run(self) -> None:
        async with MeteringUnitOfWork(self._async_engine) as uow:
            self._uow = uow
            self._event_map = {}
            try:
                await super().run()
            finally:
                self._uow = None
                self._event_map = {}

    async def claim_pending(self, limit: int) -> list[OutboxRecord]:
        assert self._uow is not None
        from sqlalchemy import func

        stmt = (
            select(OutboxEventModel)
            .where(
                OutboxEventModel.status == "pending",
                OutboxEventModel.attempts < self.MAX_ATTEMPTS,
                OutboxEventModel.available_at <= func.now(),
            )
            .order_by(OutboxEventModel.available_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._uow.session.execute(stmt)
        models = list(result.scalars().all())
        records: list[OutboxRecord] = []
        for model in models:
            self._event_map[model.id] = model
            records.append(
                OutboxRecord(
                    id=model.id,
                    aggregate_type=model.aggregate_type,
                    aggregate_id=model.aggregate_id,
                    event_type=model.event_type,
                    event_version=model.event_version,
                    payload=model.payload,
                    correlation_id=model.correlation_id,
                    causation_id=model.causation_id,
                    attempts=model.attempts,
                    error=model.error,
                )
            )
        return records

    async def publish(self, record: OutboxRecord) -> None:
        model = self._event_map.get(record.id)
        if model is None:
            raise ValueError(f"Outbox record {record.id} not in claimed batch")
        envelope = outbox_to_rabbit_message(model)
        await self._publisher.publish(envelope)

    async def mark_published(self, record: OutboxRecord) -> None:
        assert self._uow is not None
        stmt = (
            update(OutboxEventModel)
            .where(OutboxEventModel.id == record.id)
            .values(
                status="published",
                published_at=datetime.now(timezone.utc),
                attempts=OutboxEventModel.attempts + 1,
            )
        )
        await self._uow.session.execute(stmt)

    async def mark_failed(self, record: OutboxRecord, error: str) -> None:
        assert self._uow is not None
        backoff = RETRY_BACKOFF_BASE_SECONDS * (2**record.attempts)
        stmt = (
            update(OutboxEventModel)
            .where(OutboxEventModel.id == record.id)
            .values(
                status=(
                    "failed"
                    if record.attempts + 1 >= self.MAX_ATTEMPTS
                    else "pending"
                ),
                error=error,
                attempts=OutboxEventModel.attempts + 1,
                available_at=datetime.now(timezone.utc)
                + timedelta(seconds=backoff),
            )
        )
        await self._uow.session.execute(stmt)

    async def mark_dead(self, record: OutboxRecord) -> None:
        assert self._uow is not None
        stmt = (
            update(OutboxEventModel)
            .where(OutboxEventModel.id == record.id)
            .values(
                status="dead",
                error=record.error or "max attempts exceeded",
                attempts=OutboxEventModel.attempts + 1,
            )
        )
        await self._uow.session.execute(stmt)

    async def mark_retryable(self, record: OutboxRecord) -> None:
        assert self._uow is not None
        backoff = RETRY_BACKOFF_BASE_SECONDS * (2**record.attempts)
        stmt = (
            update(OutboxEventModel)
            .where(OutboxEventModel.id == record.id)
            .values(
                status="pending",
                error=record.error,
                attempts=OutboxEventModel.attempts + 1,
                available_at=datetime.now(timezone.utc)
                + timedelta(seconds=backoff),
            )
        )
        await self._uow.session.execute(stmt)
