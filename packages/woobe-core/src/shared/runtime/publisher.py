from __future__ import annotations

import asyncio
import logging
import time
from copy import deepcopy
from typing import Any
from uuid import UUID

from shared.contracts.execution_state import ExecutionStateStore
from shared.runtime.projection import (
    STRUCTURAL_RUNTIME_EVENTS,
    initial_projection,
    public_event,
    reduce_projection,
)

logger = logging.getLogger(__name__)


class RuntimeEventPublisher:
    """Best-effort hot event publisher with batched projection checkpoints.

    Runtime event delivery is observation infrastructure. Publication failures
    degrade reattach capability but never redefine the durable Run outcome.
    """

    def __init__(
        self,
        store: ExecutionStateStore,
        *,
        projection_interval_seconds: float = 0.2,
        maxlen: int = 2000,
    ) -> None:
        self._store = store
        self._projection_interval_seconds = max(0.0, projection_interval_seconds)
        self._maxlen = max(100, maxlen)
        self._last_projection_write: dict[UUID, float] = {}
        self._projection_lock = asyncio.Lock()

    @property
    def store(self) -> ExecutionStateStore:
        return self._store

    async def publish(
        self,
        run_id: UUID,
        run_kind: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        force_projection: bool | None = None,
        event_id: str | None = None,
        sequence: int | None = None,
        occurred_at: str | None = None,
    ) -> str | None:
        try:
            cursor = await self._store.append_event(
                run_id,
                event_type,
                payload,
                maxlen=self._maxlen,
                event_id=event_id, sequence=sequence, occurred_at=occurred_at,
            )
            now = time.monotonic()
            force = (
                event_type in STRUCTURAL_RUNTIME_EVENTS
                if force_projection is None
                else force_projection
            )
            last = self._last_projection_write.get(run_id, 0.0)
            if force or now - last >= self._projection_interval_seconds:
                await self._checkpoint(run_id, run_kind)
                self._last_projection_write[run_id] = now
            return cursor
        except Exception as exc:
            logger.warning(
                "Runtime event publication degraded run_id=%s event=%s: %s",
                run_id,
                event_type,
                exc,
            )
            return None

    async def _checkpoint(self, run_id: UUID, run_kind: str) -> None:
        async with self._projection_lock:
            hot = await self._store.get(run_id)
            if not hot:
                return
            high_watermark = int(hot.get("event_sequence") or 0)
            saved = hot.get("runtime_projection")
            projection = (
                deepcopy(saved)
                if isinstance(saved, dict)
                else initial_projection(run_id, run_kind, hot)
            )
            sequence = int(projection.get("sequence") or 0)
            if high_watermark <= sequence:
                return
            events = await self._store.list_events_after(
                run_id,
                sequence,
                through_sequence=high_watermark,
                limit=max(self._maxlen, high_watermark - sequence + 1),
            )
            expected = sequence + 1
            for event in events:
                if event.sequence != expected:
                    logger.warning(
                        "Runtime projection checkpoint skipped because event continuity was lost",
                        extra={
                            "run_id": str(run_id),
                            "run_kind": run_kind.upper(),
                            "projection_sequence": sequence,
                            "expected_sequence": expected,
                            "observed_sequence": event.sequence,
                            "high_watermark": high_watermark,
                        },
                    )
                    return
                public_type, public_payload = public_event(event)
                projection = reduce_projection(
                    projection,
                    public_type,
                    public_payload,
                    sequence=event.sequence,
                    occurred_at=event.occurred_at,
                )
                expected += 1
            if events and events[-1].sequence == high_watermark:
                await self._store.update(run_id, {"runtime_projection": projection})
