from __future__ import annotations

import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any

from shared.workers.base_worker import BaseWorker

logger = logging.getLogger(__name__)


@dataclass
class InboxRecord:
    outbox_origin_id: Any
    aggregate_type: str
    event_type: str
    event_version: int
    payload: dict
    correlation_id: Any | None = None
    causation_id: Any | None = None


class BaseInboxConsumer(BaseWorker):
    async def run(self) -> None:
        await self.consume()

    @abstractmethod
    async def consume(self) -> None:
        ...

    @abstractmethod
    async def persist_inbox(self, record: InboxRecord) -> None:
        ...

    @abstractmethod
    async def acknowledge(self, message: Any) -> None:
        ...

    @abstractmethod
    async def reject(self, message: Any, error: str) -> None:
        ...
