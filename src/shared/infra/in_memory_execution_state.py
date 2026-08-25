from __future__ import annotations

import asyncio
from collections import defaultdict
from copy import deepcopy
from typing import Any
from uuid import UUID

from shared.contracts.execution_state import ExecutionLease, ExecutionStateStore


class InMemoryExecutionStateStore(ExecutionStateStore):
    """Process-local fallback used by tests and explicit no-Redis development."""

    def __init__(self) -> None:
        self._states: dict[UUID, dict[str, Any]] = {}
        self._events: dict[UUID, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        self._leases: dict[UUID, tuple[str, int]] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        run_id: UUID,
        state: dict[str, Any],
        *,
        ttl_seconds: int,
    ) -> None:
        del ttl_seconds
        async with self._lock:
            self._states[run_id] = {
                "run_id": str(run_id),
                "cancel_requested": False,
                "lease_generation": 0,
                **deepcopy(state),
            }

    async def get(self, run_id: UUID) -> dict[str, Any] | None:
        state = self._states.get(run_id)
        return deepcopy(state) if state is not None else None

    async def update(self, run_id: UUID, values: dict[str, Any]) -> None:
        async with self._lock:
            state = self._states.setdefault(run_id, {"run_id": str(run_id)})
            state.update(deepcopy(values))

    async def append_event(
        self,
        run_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        *,
        maxlen: int = 2000,
    ) -> str | None:
        async with self._lock:
            events = self._events[run_id]
            events.append((event_type, deepcopy(payload)))
            if len(events) > maxlen:
                del events[: len(events) - maxlen]
            return str(len(events))

    async def request_cancel(self, run_id: UUID) -> None:
        await self.update(run_id, {"cancel_requested": True})

    async def is_cancel_requested(self, run_id: UUID) -> bool:
        state = self._states.get(run_id)
        return bool(state and state.get("cancel_requested"))

    async def acquire_lease(
        self,
        run_id: UUID,
        *,
        worker_id: str,
        ttl_seconds: int,
    ) -> ExecutionLease | None:
        del ttl_seconds
        async with self._lock:
            if run_id in self._leases:
                return None
            state = self._states.setdefault(run_id, {"run_id": str(run_id)})
            generation = int(state.get("lease_generation") or 0) + 1
            state["lease_generation"] = generation
            state["lease_owner"] = worker_id
            self._leases[run_id] = (worker_id, generation)
            return ExecutionLease(worker_id, generation)

    async def renew_lease(
        self,
        run_id: UUID,
        *,
        worker_id: str,
        ttl_seconds: int,
    ) -> bool:
        del ttl_seconds
        lease = self._leases.get(run_id)
        return bool(lease and lease[0] == worker_id)

    async def increment(
        self,
        run_id: UUID,
        field: str,
        *,
        amount: int = 1,
    ) -> int:
        async with self._lock:
            state = self._states.setdefault(run_id, {"run_id": str(run_id)})
            value = int(state.get(field) or 0) + amount
            state[field] = value
            return value

    async def expire(self, run_id: UUID, *, ttl_seconds: int) -> None:
        del run_id, ttl_seconds

    async def delete(self, run_id: UUID) -> None:
        async with self._lock:
            self._states.pop(run_id, None)
            self._events.pop(run_id, None)
            self._leases.pop(run_id, None)
