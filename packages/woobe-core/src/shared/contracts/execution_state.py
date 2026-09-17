from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class ExecutionLease:
    owner: str
    generation: int


@dataclass(frozen=True)
class ExecutionEvent:
    """Ordered runtime event retained by the hot execution store.

    `sequence` is the logical per-Run ordering used by Woobe. `cursor` is an
    infrastructure cursor used only to continue reading the underlying stream.
    """

    sequence: int
    cursor: str
    event_type: str
    payload: dict[str, Any]
    occurred_at: str
    event_id: str


class ExecutionStateStore(Protocol):
    """Fast, recoverable state for in-flight Runs.

    Implementations are operational state stores, not the durable source of truth.
    Secrets and decrypted credentials must never be written through this contract.
    """

    async def create(
        self,
        run_id: UUID,
        state: dict[str, Any],
        *,
        ttl_seconds: int,
    ) -> None: ...

    async def get(self, run_id: UUID) -> dict[str, Any] | None: ...

    async def update(
        self,
        run_id: UUID,
        values: dict[str, Any],
    ) -> None: ...

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
    ) -> str | None: ...

    async def list_events_after(
        self,
        run_id: UUID,
        sequence: int,
        *,
        through_sequence: int | None = None,
        limit: int = 2000,
    ) -> list[ExecutionEvent]: ...

    async def read_events_after_cursor(
        self,
        run_id: UUID,
        cursor: str,
        *,
        block_ms: int = 1000,
        limit: int = 100,
    ) -> list[ExecutionEvent]: ...

    async def first_event_sequence(self, run_id: UUID) -> int | None: ...

    async def request_cancel(self, run_id: UUID) -> None: ...

    async def is_cancel_requested(self, run_id: UUID) -> bool: ...

    async def acquire_lease(
        self,
        run_id: UUID,
        *,
        worker_id: str,
        ttl_seconds: int,
    ) -> ExecutionLease | None: ...

    async def renew_lease(
        self,
        run_id: UUID,
        *,
        worker_id: str,
        ttl_seconds: int,
    ) -> bool: ...

    async def increment(
        self,
        run_id: UUID,
        field: str,
        *,
        amount: int = 1,
    ) -> int: ...

    async def expire(self, run_id: UUID, *, ttl_seconds: int) -> None: ...

    async def delete(self, run_id: UUID) -> None: ...
