from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class ExecutionLease:
    owner: str
    generation: int


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
    ) -> str | None: ...

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
