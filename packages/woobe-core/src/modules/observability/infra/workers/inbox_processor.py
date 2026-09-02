from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.observability.infra.database.models import InboxEventModel
from modules.observability.infra.database.repositories import (
    OBSERVABILITY_DEFAULT_BATCH_SIZE,
    ObservabilityInboxStore,
)
from modules.observability.infra.database.unit_of_work import ObservabilityUnitOfWork
from modules.observability.infra.messaging.inbox_handlers import ObservabilityInboxEventRouter
from shared.workers.inbox_processor_base import BaseInboxProcessor, InboxProcessingRecord

logger = logging.getLogger(__name__)
RETRY_BACKOFF_BASE_SECONDS: int = 30


class ObservabilityInboxProcessorWorker(BaseInboxProcessor):
    BATCH_SIZE: int = OBSERVABILITY_DEFAULT_BATCH_SIZE
    MAX_ATTEMPTS: int = 5

    def __init__(
        self,
        async_engine: AsyncEngine,
        handler: ObservabilityInboxEventRouter,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(async_engine)
        self._handler = handler
        self._worker_id = worker_id or f"inbox-processor-{os.getpid()}"
        self._uow: ObservabilityUnitOfWork | None = None
        self._store: ObservabilityInboxStore | None = None
        self._event_map: dict[UUID, InboxEventModel] = {}

    async def run(self) -> None:
        records = await self._claim_records()
        for record in records:
            try:
                await self._process_record(record)
            except Exception as exc:
                logger.exception(
                    "Failed to process observability inbox record %s: %s",
                    record.id,
                    exc,
                )
                try:
                    await self._persist_failure(record, str(exc))
                except Exception:
                    logger.exception(
                        "Failed to persist retry state for observability inbox record %s",
                        record.id,
                    )

    async def _claim_records(self) -> list[InboxProcessingRecord]:
        async with ObservabilityUnitOfWork(self._async_engine) as uow:
            self._bind_uow(uow)
            try:
                return await self.claim_pending(limit=self.BATCH_SIZE)
            finally:
                self._clear_uow()

    async def _process_record(self, record: InboxProcessingRecord) -> None:
        async with ObservabilityUnitOfWork(self._async_engine) as uow:
            self._bind_uow(uow)
            try:
                await self.process(record)
                await self.mark_processed(record)
            finally:
                self._clear_uow()

    async def _persist_failure(
        self,
        record: InboxProcessingRecord,
        error: str,
    ) -> None:
        async with ObservabilityUnitOfWork(self._async_engine) as uow:
            self._bind_uow(uow)
            try:
                await self.mark_failed(record, error)
            finally:
                self._clear_uow()

    def _bind_uow(self, uow: ObservabilityUnitOfWork) -> None:
        self._uow = uow
        self._store = ObservabilityInboxStore(uow)
        self._event_map = {}

    def _clear_uow(self) -> None:
        self._uow = None
        self._store = None
        self._event_map = {}

    async def claim_pending(self, limit: int) -> list[InboxProcessingRecord]:
        assert self._store is not None
        events = await self._store.claim_batch(
            batch_size=limit,
            locked_by=self._worker_id,
        )
        records: list[InboxProcessingRecord] = []
        for event in events:
            record = InboxProcessingRecord(
                id=event.id,
                outbox_origin_id=event.outbox_origin_id or event.message_id,
                aggregate_type=event.producer_module or "unknown",
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

    async def process(self, record: InboxProcessingRecord) -> None:
        assert self._uow is not None
        await self._handler.handle(
            event_type=record.event_type,
            payload=record.payload,
            correlation_id=record.correlation_id,
            causation_id=record.causation_id,
            event_version=record.event_version,
            uow=self._uow,
        )

    async def mark_processed(self, record: InboxProcessingRecord) -> None:
        assert self._store is not None
        await self._store.mark_processed(record.id)

    async def mark_dead(self, record: InboxProcessingRecord) -> None:
        assert self._store is not None
        await self._store.mark_dead(
            record.id,
            record.error or "max attempts exceeded",
        )

    async def mark_retryable(self, record: InboxProcessingRecord) -> None:
        assert self._store is not None
        backoff = timedelta(
            seconds=RETRY_BACKOFF_BASE_SECONDS * (record.attempts + 1)
        )
        available_at = datetime.now(timezone.utc) + backoff
        await self._store.mark_retryable(
            record.id,
            record.error or "transient failure",
            available_at,
        )
