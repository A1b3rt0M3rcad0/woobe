from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from modules.observability.background_boundary import InboxEventModel
from modules.observability.background_boundary import (
    OBSERVABILITY_DEFAULT_BATCH_SIZE,
    SQLAlchemyObservabilityInboxRepository,
)
from modules.observability.background_boundary import ObservabilityInboxEventRouter
from woobe_workers.runtime.inbox_processor_base import BaseInboxProcessor, InboxProcessingRecord

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
        self._session: AsyncSession | None = None
        self._repo: SQLAlchemyObservabilityInboxRepository | None = None
        self._event_map: dict[UUID, InboxEventModel] = {}

    async def run(self) -> None:
        async with AsyncSession(self._async_engine) as session:
            async with session.begin():
                self._session = session
                self._repo = SQLAlchemyObservabilityInboxRepository(session)
                self._event_map = {}
                await super().run()
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
                outbox_origin_id=event.message_id,
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
        await self._handler.handle(
            event_type=record.event_type,
            payload=record.payload,
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
