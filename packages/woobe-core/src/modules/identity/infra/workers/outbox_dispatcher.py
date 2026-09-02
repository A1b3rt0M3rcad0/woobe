"""Identity outbox dispatcher with short database transactions around external publish work."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from modules.identity.infra.database.models import OutboxEventModel
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.infra.messaging.event_mappers import (
    RabbitMQMessageEnvelope,
    outbox_to_rabbit_message,
)
from shared.workers.outbox_dispatcher_base import BaseOutboxDispatcher, OutboxRecord

logger = logging.getLogger(__name__)

IDENTITY_OUTBOX_BATCH_SIZE: int = 50
IDENTITY_OUTBOX_MAX_ATTEMPTS: int = 5
IDENTITY_OUTBOX_LOCK_TIMEOUT_SECONDS: int = 300
RETRY_BACKOFF_BASE_SECONDS: int = 30


class IdentityOutboxPublisherProtocol(Protocol):
    async def publish(self, envelope: RabbitMQMessageEnvelope) -> None: ...


class IdentityOutboxDispatcherWorker(BaseOutboxDispatcher):
    BATCH_SIZE: int = IDENTITY_OUTBOX_BATCH_SIZE
    MAX_ATTEMPTS: int = IDENTITY_OUTBOX_MAX_ATTEMPTS

    def __init__(
        self,
        async_engine: AsyncEngine,
        publisher: IdentityOutboxPublisherProtocol,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(async_engine)
        self._publisher = publisher
        self._worker_id = worker_id or f"identity-outbox-dispatcher-{os.getpid()}"
        self._envelope_map: dict[UUID, RabbitMQMessageEnvelope] = {}

    async def run(self) -> None:
        records = await self.claim_pending(limit=self.BATCH_SIZE)
        if not records:
            return

        published: list[OutboxRecord] = []
        failed: list[OutboxRecord] = []
        for record in records:
            try:
                await self.publish(record)
                published.append(record)
            except Exception as exc:
                logger.exception(
                    "Failed to publish Identity outbox record %s: %s",
                    record.id,
                    exc,
                )
                record.error = str(exc)
                failed.append(record)

        async with IdentityUnitOfWork(self._async_engine) as uow:
            for record in published:
                await self._mark_published(uow, record)
            for record in failed:
                await self._mark_failed(uow, record)
        self._envelope_map = {}

    async def claim_pending(self, limit: int) -> list[OutboxRecord]:
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=IDENTITY_OUTBOX_LOCK_TIMEOUT_SECONDS)
        records: list[OutboxRecord] = []
        envelope_map: dict[UUID, RabbitMQMessageEnvelope] = {}

        async with IdentityUnitOfWork(self._async_engine) as uow:
            statement = (
                select(OutboxEventModel)
                .where(
                    OutboxEventModel.status == "pending",
                    OutboxEventModel.attempts < self.MAX_ATTEMPTS,
                    OutboxEventModel.available_at <= func.now(),
                    or_(
                        OutboxEventModel.locked_at.is_(None),
                        OutboxEventModel.locked_at < stale_before,
                    ),
                )
                .order_by(OutboxEventModel.available_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            result = await uow.session.execute(statement)
            models = list(result.scalars().all())
            for model in models:
                model.locked_at = now
                model.locked_by = self._worker_id
                records.append(self._record(model))
                envelope_map[model.id] = outbox_to_rabbit_message(model)

        self._envelope_map = envelope_map
        return records

    @staticmethod
    def _record(model: OutboxEventModel) -> OutboxRecord:
        return OutboxRecord(
            id=model.id,
            aggregate_type=model.aggregate_type,
            aggregate_id=model.aggregate_id,
            event_type=model.event_type,
            event_version=model.event_version,
            payload=model.payload or {},
            correlation_id=model.correlation_id,
            causation_id=model.causation_id,
            attempts=model.attempts,
            error=model.error,
        )

    async def publish(self, record: OutboxRecord) -> None:
        envelope = self._envelope_map.get(record.id)
        if envelope is None:
            raise ValueError(f"Outbox record {record.id} not in claimed batch")
        await self._publisher.publish(envelope)

    async def _mark_published(
        self,
        uow: IdentityUnitOfWork,
        record: OutboxRecord,
    ) -> None:
        await uow.session.execute(
            update(OutboxEventModel)
            .where(
                OutboxEventModel.id == record.id,
                OutboxEventModel.locked_by == self._worker_id,
            )
            .values(
                status="published",
                published_at=datetime.now(timezone.utc),
                attempts=OutboxEventModel.attempts + 1,
                locked_at=None,
                locked_by=None,
                error=None,
            )
        )

    async def _mark_failed(
        self,
        uow: IdentityUnitOfWork,
        record: OutboxRecord,
    ) -> None:
        backoff = RETRY_BACKOFF_BASE_SECONDS * (2**record.attempts)
        terminal = record.attempts + 1 >= self.MAX_ATTEMPTS
        await uow.session.execute(
            update(OutboxEventModel)
            .where(
                OutboxEventModel.id == record.id,
                OutboxEventModel.locked_by == self._worker_id,
            )
            .values(
                status="failed" if terminal else "pending",
                error=record.error,
                attempts=OutboxEventModel.attempts + 1,
                available_at=datetime.now(timezone.utc) + timedelta(seconds=backoff),
                locked_at=None,
                locked_by=None,
            )
        )

    async def mark_published(self, record: OutboxRecord) -> None:
        async with IdentityUnitOfWork(self._async_engine) as uow:
            await self._mark_published(uow, record)

    async def mark_failed(self, record: OutboxRecord, error: str) -> None:
        record.error = error
        async with IdentityUnitOfWork(self._async_engine) as uow:
            await self._mark_failed(uow, record)

    async def mark_dead(self, record: OutboxRecord) -> None:
        async with IdentityUnitOfWork(self._async_engine) as uow:
            await uow.session.execute(
                update(OutboxEventModel)
                .where(
                    OutboxEventModel.id == record.id,
                    OutboxEventModel.locked_by == self._worker_id,
                )
                .values(
                    status="failed",
                    error=record.error or "max attempts exceeded",
                    attempts=OutboxEventModel.attempts + 1,
                    locked_at=None,
                    locked_by=None,
                )
            )

    async def mark_retryable(self, record: OutboxRecord) -> None:
        async with IdentityUnitOfWork(self._async_engine) as uow:
            await self._mark_failed(uow, record)
