from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from modules.metering.infra.database.models import InboxEventModel
from modules.metering.infra.database.repositories import (
    METERING_DEFAULT_BATCH_SIZE,
    SQLAlchemyMeteringInboxRepository,
)
from modules.metering.infra.messaging.inbox_handlers import MeteringInboxEventRouter
from shared.workers.inbox_processor_base import BaseInboxProcessor, InboxProcessingRecord

logger = logging.getLogger(__name__)

RETRY_BACKOFF_BASE_SECONDS: int = 30


class MeteringInboxProcessorWorker(BaseInboxProcessor):
    BATCH_SIZE: int = METERING_DEFAULT_BATCH_SIZE
    MAX_ATTEMPTS: int = 5

    def __init__(
        self,
        async_engine: AsyncEngine,
        handler: MeteringInboxEventRouter,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(async_engine)
        self._handler = handler
        self._worker_id = worker_id or f"inbox-processor-{os.getpid()}"
        self._session: AsyncSession | None = None
        self._repo: SQLAlchemyMeteringInboxRepository | None = None
        self._event_map: dict[UUID, InboxEventModel] = {}

    async def run(self) -> None:
        records = await self._claim_records()
        for record in records:
            try:
                await self._process_record(record)
            except Exception as exc:
                logger.exception(
                    "Failed to process metering inbox record %s: %s",
                    record.id,
                    exc,
                )
                try:
                    await self._persist_failure(record, str(exc))
                except Exception:
                    logger.exception(
                        "Failed to persist retry state for metering inbox record %s",
                        record.id,
                    )

    async def _claim_records(self) -> list[InboxProcessingRecord]:
        async with AsyncSession(self._async_engine) as session:
            async with session.begin():
                self._bind_session(session)
                try:
                    return await self.claim_pending(limit=self.BATCH_SIZE)
                finally:
                    self._clear_session()

    async def _process_record(self, record: InboxProcessingRecord) -> None:
        async with AsyncSession(self._async_engine) as session:
            async with session.begin():
                self._bind_session(session)
                try:
                    await self.process(record)
                    await self.mark_processed(record)
                finally:
                    self._clear_session()

    async def _persist_failure(
        self,
        record: InboxProcessingRecord,
        error: str,
    ) -> None:
        async with AsyncSession(self._async_engine) as session:
            async with session.begin():
                self._bind_session(session)
                try:
                    await self.mark_failed(record, error)
                finally:
                    self._clear_session()

    def _bind_session(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SQLAlchemyMeteringInboxRepository(session)
        self._event_map = {}

    def _clear_session(self) -> None:
        self._session = None
        self._repo = None
        self._event_map = {}

    async def claim_pending(self, limit: int) -> list[InboxProcessingRecord]:
        assert self._repo is not None
        events = await self._repo.claim_batch(
            batch_size=limit, locked_by=self._worker_id
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
        assert self._session is not None
        source_event_id = None
        try:
            source_event_id = UUID(str(record.outbox_origin_id))
        except (TypeError, ValueError):
            logger.warning(
                "Metering inbox record %s has no valid source event id",
                record.id,
            )
        await self._handler.handle(
            event_type=record.event_type,
            payload=record.payload,
            source_event_id=source_event_id,
            correlation_id=record.correlation_id,
            causation_id=record.causation_id,
            event_version=record.event_version,
            session=self._session,
        )

    async def mark_processed(self, record: InboxProcessingRecord) -> None:
        assert self._repo is not None
        await self._repo.mark_processed(record.id)

    async def mark_dead(self, record: InboxProcessingRecord) -> None:
        assert self._repo is not None
        await self._repo.mark_dead(record.id, record.error or "max attempts exceeded")

    async def mark_retryable(self, record: InboxProcessingRecord) -> None:
        assert self._repo is not None
        backoff = timedelta(seconds=RETRY_BACKOFF_BASE_SECONDS * (record.attempts + 1))
        available_at = datetime.now(timezone.utc) + backoff
        await self._repo.mark_retryable(
            record.id, record.error or "transient failure", available_at
        )
