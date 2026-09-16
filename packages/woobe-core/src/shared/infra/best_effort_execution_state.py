from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from shared.contracts.execution_state import ExecutionEvent, ExecutionLease, ExecutionStateStore

logger = logging.getLogger(__name__)


class BestEffortExecutionStateStore(ExecutionStateStore):
    """Make hot-state writes non-fatal for standalone Agent execution.

    PostgreSQL remains the durable source of truth. This wrapper is intentionally
    not used by Network execution ownership, where Redis state is required for the
    orchestrator itself.
    """

    def __init__(self, inner: ExecutionStateStore) -> None:
        self._inner = inner

    async def _write(self, operation, *, default=None):
        try:
            return await operation()
        except Exception as exc:
            logger.warning("Hot execution state write degraded: %s", exc)
            return default

    async def create(self, run_id: UUID, state: dict[str, Any], *, ttl_seconds: int) -> None:
        await self._write(lambda: self._inner.create(run_id, state, ttl_seconds=ttl_seconds))

    async def get(self, run_id: UUID) -> dict[str, Any] | None:
        return await self._inner.get(run_id)

    async def update(self, run_id: UUID, values: dict[str, Any]) -> None:
        await self._write(lambda: self._inner.update(run_id, values))

    async def append_event(
        self,
        run_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        *,
        maxlen: int = 2000,
        event_id: str | None = None,
        sequence: int | None = None,
        occurred_at: str | None = None,
    ) -> str | None:
        return await self._write(
            lambda: self._inner.append_event(
                run_id, event_type, payload, maxlen=maxlen,
                event_id=event_id, sequence=sequence, occurred_at=occurred_at,
            )
        )

    async def list_events_after(
        self,
        run_id: UUID,
        sequence: int,
        *,
        through_sequence: int | None = None,
        limit: int = 2000,
    ) -> list[ExecutionEvent]:
        return await self._inner.list_events_after(
            run_id,
            sequence,
            through_sequence=through_sequence,
            limit=limit,
        )

    async def read_events_after_cursor(
        self,
        run_id: UUID,
        cursor: str,
        *,
        block_ms: int = 1000,
        limit: int = 100,
    ) -> list[ExecutionEvent]:
        return await self._inner.read_events_after_cursor(
            run_id,
            cursor,
            block_ms=block_ms,
            limit=limit,
        )

    async def first_event_sequence(self, run_id: UUID) -> int | None:
        return await self._inner.first_event_sequence(run_id)

    async def request_cancel(self, run_id: UUID) -> None:
        await self._write(lambda: self._inner.request_cancel(run_id))

    async def is_cancel_requested(self, run_id: UUID) -> bool:
        return await self._inner.is_cancel_requested(run_id)

    async def acquire_lease(
        self,
        run_id: UUID,
        *,
        worker_id: str,
        ttl_seconds: int,
    ) -> ExecutionLease | None:
        return await self._inner.acquire_lease(
            run_id,
            worker_id=worker_id,
            ttl_seconds=ttl_seconds,
        )

    async def renew_lease(
        self,
        run_id: UUID,
        *,
        worker_id: str,
        ttl_seconds: int,
    ) -> bool:
        return await self._inner.renew_lease(
            run_id,
            worker_id=worker_id,
            ttl_seconds=ttl_seconds,
        )

    async def increment(
        self,
        run_id: UUID,
        field: str,
        *,
        amount: int = 1,
    ) -> int:
        return await self._inner.increment(run_id, field, amount=amount)

    async def expire(self, run_id: UUID, *, ttl_seconds: int) -> None:
        await self._write(lambda: self._inner.expire(run_id, ttl_seconds=ttl_seconds))

    async def delete(self, run_id: UUID) -> None:
        await self._write(lambda: self._inner.delete(run_id))
