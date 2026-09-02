from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from modules.core.infra.database.models import InboxEventModel
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.workers.inbox_processor_base import BaseInboxProcessor, InboxProcessingRecord

logger = logging.getLogger(__name__)

CORE_INBOX_BATCH_SIZE: int = 50
CORE_INBOX_MAX_ATTEMPTS: int = 5
CORE_INBOX_LOCK_TIMEOUT_SECONDS: int = 300
RETRY_BACKOFF_BASE_SECONDS: int = 30


class CoreInboxHandlerProtocol(Protocol):
    async def handle(
        self,
        event_type: str,
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> None: ...


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
        self._uow: CoreUnitOfWork | None = None

    async def run(self) -> None:
        records = await self._claim_records()
        for record in records:
            try:
                await self._process_record(record)
            except Exception as exc:
                logger.exception(
                    "Failed to process Core inbox record %s: %s",
                    record.id,
                    exc,
                )
                await self._persist_failure(record, str(exc))

    async def _claim_records(self) -> list[InboxProcessingRecord]:
        async with CoreUnitOfWork(self._async_engine) as uow:
            self._uow = uow
            try:
                return await self.claim_pending(limit=self.BATCH_SIZE)
            finally:
                self._uow = None

    async def _process_record(self, record: InboxProcessingRecord) -> None:
        async with CoreUnitOfWork(self._async_engine) as uow:
            self._uow = uow
            try:
                await self.process(record)
                await self.mark_processed(record)
            finally:
                self._uow = None

    async def _persist_failure(
        self,
        record: InboxProcessingRecord,
        error: str,
    ) -> None:
        async with CoreUnitOfWork(self._async_engine) as uow:
            self._uow = uow
            try:
                await self.mark_failed(record, error)
            finally:
                self._uow = None

    async def claim_pending(self, limit: int) -> list[InboxProcessingRecord]:
        assert self._uow is not None
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=CORE_INBOX_LOCK_TIMEOUT_SECONDS)
        statement = (
            select(InboxEventModel)
            .where(
                InboxEventModel.status == "pending",
                InboxEventModel.attempts < self.MAX_ATTEMPTS,
                InboxEventModel.available_at <= func.now(),
                or_(
                    InboxEventModel.locked_at.is_(None),
                    InboxEventModel.locked_at < stale_before,
                ),
            )
            .order_by(InboxEventModel.available_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._uow.session.execute(statement)
        models = list(result.scalars().all())
        records: list[InboxProcessingRecord] = []
        for model in models:
            model.locked_at = now
            model.locked_by = self._worker_id
            records.append(
                InboxProcessingRecord(
                    id=model.id,
                    outbox_origin_id=model.outbox_origin_id or model.message_id,
                    aggregate_type=model.aggregate_type,
                    event_type=model.event_type,
                    event_version=model.event_version,
                    payload=model.payload or {},
                    correlation_id=model.correlation_id,
                    causation_id=model.causation_id,
                    attempts=model.attempts,
                    error=model.error,
                )
            )
        return records

    async def process(self, record: InboxProcessingRecord) -> None:
        await self._handler.handle(record.event_type, record.payload)

    async def mark_processed(self, record: InboxProcessingRecord) -> None:
        assert self._uow is not None
        await self._uow.session.execute(
            update(InboxEventModel)
            .where(
                InboxEventModel.id == record.id,
                InboxEventModel.locked_by == self._worker_id,
            )
            .values(
                status="processed",
                processed_at=datetime.now(timezone.utc),
                attempts=InboxEventModel.attempts + 1,
                locked_at=None,
                locked_by=None,
                error=None,
            )
        )

    async def mark_dead(self, record: InboxProcessingRecord) -> None:
        assert self._uow is not None
        await self._uow.session.execute(
            update(InboxEventModel)
            .where(
                InboxEventModel.id == record.id,
                InboxEventModel.locked_by == self._worker_id,
            )
            .values(
                status="failed",
                error=record.error or "max attempts exceeded",
                attempts=record.attempts,
                locked_at=None,
                locked_by=None,
            )
        )

    async def mark_retryable(self, record: InboxProcessingRecord) -> None:
        assert self._uow is not None
        await self._uow.session.execute(
            update(InboxEventModel)
            .where(
                InboxEventModel.id == record.id,
                InboxEventModel.locked_by == self._worker_id,
            )
            .values(
                status="pending",
                error=record.error,
                attempts=record.attempts,
                available_at=datetime.now(timezone.utc)
                + timedelta(
                    seconds=RETRY_BACKOFF_BASE_SECONDS
                    * (2 ** max(record.attempts - 1, 0))
                ),
                locked_at=None,
                locked_by=None,
            )
        )
