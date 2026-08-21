"""Agent inbox processor worker — claims pending inbox events and delegates to handlers."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.infra.database.models import AgentInboxEventModel
from modules.agent.infra.database.repositories import (
    AGENT_DEFAULT_BATCH_SIZE,
    SQLAlchemyAgentInboxRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.workers.inbox_processor_base import BaseInboxProcessor, InboxProcessingRecord

logger = logging.getLogger(__name__)

RETRY_BACKOFF_BASE_SECONDS: int = 30


class AgentInboxHandlerProtocol(Protocol):
    async def handle(self, event_type: str, payload: dict[str, Any], **kwargs: Any) -> None: ...


class AgentInboxProcessorWorker(BaseInboxProcessor):
    BATCH_SIZE: int = AGENT_DEFAULT_BATCH_SIZE
    MAX_ATTEMPTS: int = 5

    def __init__(
        self,
        async_engine: AsyncEngine,
        handler: AgentInboxHandlerProtocol,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(async_engine)
        self._handler = handler
        self._worker_id = worker_id or f"inbox-processor-{os.getpid()}"
        self._repo: SQLAlchemyAgentInboxRepository | None = None
        self._event_map: dict[UUID, AgentInboxEventModel] = {}

    async def run(self) -> None:
        async with AgentUnitOfWork(self._async_engine) as uow:
            self._repo = SQLAlchemyAgentInboxRepository(uow)
            self._event_map = {}
            await super().run()
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
