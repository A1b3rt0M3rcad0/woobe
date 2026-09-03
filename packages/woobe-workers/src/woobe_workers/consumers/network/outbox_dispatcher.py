from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from modules.network.background_boundary import NetworkOutboxEventModel
from shared.infra.rabbitmq import RabbitMQManager

logger = logging.getLogger(__name__)

_NETWORK_OUTBOX_BATCH_SIZE = 50
_NETWORK_OUTBOX_MAX_ATTEMPTS = 5
_NETWORK_OUTBOX_LOCK_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class _ClaimedNetworkOutbox:
    id: UUID
    routing_key: str
    payload: dict
    correlation_id: UUID | None
    attempts: int


class NetworkOutboxDispatcherWorker:
    """Publishes Network outbox events without holding database locks during broker I/O."""

    def __init__(
        self,
        engine: AsyncEngine,
        manager: RabbitMQManager,
        *,
        batch_size: int = _NETWORK_OUTBOX_BATCH_SIZE,
    ) -> None:
        self._session_factory = async_sessionmaker(engine, expire_on_commit=False)
        self._manager = manager
        self._worker_id = f"network-outbox-{os.getpid()}"
        self._batch_size = max(1, batch_size)

    async def run(self) -> None:
        records = await self._claim_batch()
        if not records:
            return

        results: list[tuple[_ClaimedNetworkOutbox, Exception | None]] = []
        for record in records:
            try:
                await self._manager.publish(
                    routing_key=record.routing_key,
                    payload=json.dumps(record.payload),
                    correlation_id=str(record.correlation_id or ""),
                    message_id=str(record.id),
                )
                results.append((record, None))
            except Exception as exc:
                logger.exception(
                    "Network outbox publish failed event_id=%s", record.id
                )
                results.append((record, exc))

        await self._finalize(results)

    async def _claim_batch(self) -> list[_ClaimedNetworkOutbox]:
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(
            seconds=_NETWORK_OUTBOX_LOCK_TIMEOUT_SECONDS
        )
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                select(NetworkOutboxEventModel)
                .where(
                    NetworkOutboxEventModel.status.in_(["pending", "retryable"]),
                    NetworkOutboxEventModel.available_at <= now,
                    or_(
                        NetworkOutboxEventModel.locked_at.is_(None),
                        NetworkOutboxEventModel.locked_at < stale_before,
                    ),
                )
                .order_by(NetworkOutboxEventModel.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(self._batch_size)
            )
            events = list(result.scalars())
            for event in events:
                event.locked_at = now
                event.locked_by = self._worker_id

            return [
                _ClaimedNetworkOutbox(
                    id=event.id,
                    routing_key=event.routing_key,
                    payload=event.payload or {},
                    correlation_id=event.correlation_id,
                    attempts=event.attempts,
                )
                for event in events
            ]

    async def _finalize(
        self,
        results: list[tuple[_ClaimedNetworkOutbox, Exception | None]],
    ) -> None:
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session, session.begin():
            for record, error in results:
                if error is None:
                    await session.execute(
                        update(NetworkOutboxEventModel)
                        .where(
                            NetworkOutboxEventModel.id == record.id,
                            NetworkOutboxEventModel.locked_by == self._worker_id,
                        )
                        .values(
                            status="published",
                            published_at=now,
                            locked_at=None,
                            locked_by=None,
                            error=None,
                        )
                    )
                    continue

                attempts = record.attempts + 1
                await session.execute(
                    update(NetworkOutboxEventModel)
                    .where(
                        NetworkOutboxEventModel.id == record.id,
                        NetworkOutboxEventModel.locked_by == self._worker_id,
                    )
                    .values(
                        attempts=attempts,
                        status="dead"
                        if attempts >= _NETWORK_OUTBOX_MAX_ATTEMPTS
                        else "retryable",
                        error=str(error)[:4000],
                        available_at=now
                        + timedelta(seconds=min(300, 2**attempts)),
                        locked_at=None,
                        locked_by=None,
                    )
                )
