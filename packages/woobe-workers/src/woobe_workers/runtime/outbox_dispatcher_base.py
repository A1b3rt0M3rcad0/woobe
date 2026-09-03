from __future__ import annotations

import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any

from woobe_workers.runtime.base_worker import BaseWorker

logger = logging.getLogger(__name__)


@dataclass
class OutboxRecord:
    id: Any
    aggregate_type: str
    aggregate_id: Any
    event_type: str
    event_version: int
    payload: dict
    correlation_id: Any | None = None
    causation_id: Any | None = None
    attempts: int = 0
    error: str | None = None


class BaseOutboxDispatcher(BaseWorker):
    MAX_ATTEMPTS: int = 5
    BATCH_SIZE: int = 50

    async def run(self) -> None:
        records = await self.claim_pending(limit=self.BATCH_SIZE)
        for record in records:
            try:
                await self.publish(record)
                await self.mark_published(record)
            except Exception as exc:
                logger.exception("Failed to publish outbox record %s: %s", record.id, exc)
                await self.mark_failed(record, str(exc))

    @abstractmethod
    async def claim_pending(self, limit: int) -> list[OutboxRecord]:
        ...

    @abstractmethod
    async def publish(self, record: OutboxRecord) -> None:
        ...

    @abstractmethod
    async def mark_published(self, record: OutboxRecord) -> None:
        ...

    async def mark_failed(self, record: OutboxRecord, error: str) -> None:
        record.attempts += 1
        record.error = error
        if record.attempts >= self.MAX_ATTEMPTS:
            await self.mark_dead(record)
        else:
            await self.mark_retryable(record)

    @abstractmethod
    async def mark_dead(self, record: OutboxRecord) -> None:
        ...

    @abstractmethod
    async def mark_retryable(self, record: OutboxRecord) -> None:
        ...
