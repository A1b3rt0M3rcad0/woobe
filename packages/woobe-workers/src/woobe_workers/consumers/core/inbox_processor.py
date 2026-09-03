from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from modules.core.background_boundary import InboxEventModel
from woobe_workers.runtime.inbox_processor_base import BaseInboxProcessor, InboxProcessingRecord

logger = logging.getLogger(__name__)

CORE_INBOX_BATCH_SIZE: int = 50
CORE_INBOX_MAX_ATTEMPTS: int = 5
RETRY_BACKOFF_BASE_SECONDS: int = 30


class CoreInboxHandlerProtocol(Protocol):
    async def handle(self, event_type: str, payload: dict[str, Any], **kwargs: Any) -> None: ...


class CoreInboxProcessorWorker(BaseInboxProcessor):
    BATCH_SIZE: int = CORE_INBOX_BATCH_SIZE
    MAX_ATTEMPTS: int = CORE_INBOX_MAX_ATTEMPTS

    def __init__(
        self,
        async_engine: AsyncEngine,
        handler: CoreInboxHandlerProtocol,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(async_engine)
        self._handler = handler
        self._worker_id = worker_id or f"core-inbox-processor-{os.getpid()}"
        self._session: AsyncSession | None = None
        self._event_map: dict[UUID, InboxEventModel] = {}

    async def run(self) -> None:
        async with AsyncSession(self._async_engine) as session:
            async with session.begin():
                self._session = session
                self._event_map = {}
                await super().run()
        self._session = None
        self._event_map = {}

    async def claim_pending(self, limit: int) -> list[InboxProcessingRecord]:
        assert self._session is not None
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        stmt = (
            select(InboxEventModel)
            .where(
                InboxEventModel.status == "pending",
                InboxEventModel.attempts < self.MAX_ATTEMPTS,
                InboxEventModel.available_at <= cutoff,
            )
            .order_by(InboxEventModel.available_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())
        records = []
        for m in models:
            self._event_map[m.id] = m
            records.append(
                InboxProcessingRecord(
                    id=m.id,
                    outbox_origin_id=m.outbox_origin_id,
                    aggregate_type=m.aggregate_type,
                    event_type=m.event_type,
                    event_version=m.event_version,
                    payload=m.payload,
                    correlation_id=m.correlation_id,
                    causation_id=m.causation_id,
                    attempts=m.attempts,
                    error=m.error,
                )
            )
        return records

    async def process(self, record: InboxProcessingRecord) -> None:
        await self._handler.handle(record.event_type, record.payload)

    async def mark_processed(self, record: InboxProcessingRecord) -> None:
        assert self._session is not None
        stmt = (
            update(InboxEventModel)
            .where(InboxEventModel.id == record.id)
            .values(
                status="processed",
                processed_at=datetime.now(timezone.utc),
                attempts=InboxEventModel.attempts + 1,
            )
        )
        await self._session.execute(stmt)

    async def mark_failed(self, record: InboxProcessingRecord, error: str) -> None:
        await super().mark_failed(record, error)

    async def mark_dead(self, record: InboxProcessingRecord) -> None:
        assert self._session is not None
        stmt = (
            update(InboxEventModel)
            .where(InboxEventModel.id == record.id)
            .values(
                status="failed",
                error=record.error,
                attempts=record.attempts,
            )
        )
        await self._session.execute(stmt)

    async def mark_retryable(self, record: InboxProcessingRecord) -> None:
        assert self._session is not None
        stmt = (
            update(InboxEventModel)
            .where(InboxEventModel.id == record.id)
            .values(
                status="pending",
                error=record.error,
                attempts=record.attempts,
                available_at=datetime.now(timezone.utc)
                + timedelta(seconds=RETRY_BACKOFF_BASE_SECONDS * (2 ** (record.attempts - 1))),
            )
        )
        await self._session.execute(stmt)
