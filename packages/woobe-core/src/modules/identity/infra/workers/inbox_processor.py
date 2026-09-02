"""Identity inbox processor with short claim/finalization transactions."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from modules.identity.infra.database.models import InboxEventModel
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from shared.workers.inbox_processor_base import BaseInboxProcessor, InboxProcessingRecord

logger = logging.getLogger(__name__)

IDENTITY_INBOX_BATCH_SIZE: int = 50
IDENTITY_INBOX_MAX_ATTEMPTS: int = 5
IDENTITY_INBOX_LOCK_TIMEOUT_SECONDS: int = 300
RETRY_BACKOFF_BASE_SECONDS: int = 30


class IdentityInboxHandlerProtocol(Protocol):
    async def handle(
        self,
        event_type: str,
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> None: ...


class IdentityInboxProcessorWorker(BaseInboxProcessor):
    BATCH_SIZE: int = IDENTITY_INBOX_BATCH_SIZE
    MAX_ATTEMPTS: int = IDENTITY_INBOX_MAX_ATTEMPTS

    def __init__(
        self,
        async_engine: AsyncEngine,
        handler: IdentityInboxHandlerProtocol,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(async_engine)
        self._handler = handler
        self._worker_id = worker_id or f"identity-inbox-processor-{os.getpid()}"

    async def run(self) -> None:
        records = await self.claim_pending(limit=self.BATCH_SIZE)
        for record in records:
            try:
                await self.process(record)
            except Exception as exc:
                logger.exception(
                    "Failed to process Identity inbox record %s: %s",
                    record.id,
                    exc,
                )
                await self.mark_failed(record, str(exc))
            else:
                await self.mark_processed(record)

    async def claim_pending(self, limit: int) -> list[InboxProcessingRecord]:
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=IDENTITY_INBOX_LOCK_TIMEOUT_SECONDS)
        records: list[InboxProcessingRecord] = []

        async with IdentityUnitOfWork(self._async_engine) as uow:
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
            result = await uow.session.execute(statement)
            for model in result.scalars().all():
                model.locked_at = now
                model.locked_by = self._worker_id
                records.append(
                    InboxProcessingRecord(
                        id=model.id,
                        outbox_origin_id=model.outbox_origin_id,
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
        async with IdentityUnitOfWork(self._async_engine) as uow:
            await uow.session.execute(
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

    async def mark_failed(self, record: InboxProcessingRecord, error: str) -> None:
        record.error = error
        if record.attempts + 1 >= self.MAX_ATTEMPTS:
            await self.mark_dead(record)
        else:
            await self.mark_retryable(record)

    async def mark_dead(self, record: InboxProcessingRecord) -> None:
        async with IdentityUnitOfWork(self._async_engine) as uow:
            await uow.session.execute(
                update(InboxEventModel)
                .where(
                    InboxEventModel.id == record.id,
                    InboxEventModel.locked_by == self._worker_id,
                )
                .values(
                    status="failed",
                    error=record.error or "max attempts exceeded",
                    attempts=InboxEventModel.attempts + 1,
                    locked_at=None,
                    locked_by=None,
                )
            )

    async def mark_retryable(self, record: InboxProcessingRecord) -> None:
        backoff = RETRY_BACKOFF_BASE_SECONDS * (2**record.attempts)
        async with IdentityUnitOfWork(self._async_engine) as uow:
            await uow.session.execute(
                update(InboxEventModel)
                .where(
                    InboxEventModel.id == record.id,
                    InboxEventModel.locked_by == self._worker_id,
                )
                .values(
                    status="pending",
                    error=record.error,
                    attempts=InboxEventModel.attempts + 1,
                    available_at=datetime.now(timezone.utc) + timedelta(seconds=backoff),
                    locked_at=None,
                    locked_by=None,
                )
            )
