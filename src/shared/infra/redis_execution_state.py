from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from shared.contracts.execution_state import ExecutionLease, ExecutionStateStore


_ACQUIRE_LEASE_SCRIPT = """
local lease_key = KEYS[1]
local state_key = KEYS[2]
local owner = ARGV[1]
local ttl_ms = tonumber(ARGV[2])
if redis.call('SET', lease_key, owner, 'NX', 'PX', ttl_ms) then
  local generation = redis.call('HINCRBY', state_key, 'lease_generation', 1)
  redis.call('HSET', state_key, 'lease_owner', owner)
  return generation
end
return 0
"""

_RENEW_LEASE_SCRIPT = """
local lease_key = KEYS[1]
local state_key = KEYS[2]
local owner = ARGV[1]
local ttl_ms = tonumber(ARGV[2])
if redis.call('GET', lease_key) == owner then
  redis.call('PEXPIRE', lease_key, ttl_ms)
  redis.call('HSET', state_key, 'lease_owner', owner)
  return 1
end
return 0
"""


class RedisExecutionStateStore(ExecutionStateStore):
    """Redis-backed hot state for active Agent and Network Runs."""

    def __init__(self, client: Redis, *, key_prefix: str = "woobe:execution") -> None:
        self._client = client
        self._prefix = key_prefix.strip(":")

    def _state_key(self, run_id: UUID) -> str:
        return f"{self._prefix}:run:{run_id}"

    def _events_key(self, run_id: UUID) -> str:
        return f"{self._prefix}:run:{run_id}:events"

    def _lease_key(self, run_id: UUID) -> str:
        return f"{self._prefix}:run:{run_id}:lease"

    @staticmethod
    def _encode(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def _decode(value: str) -> Any:
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value

    async def create(
        self,
        run_id: UUID,
        state: dict[str, Any],
        *,
        ttl_seconds: int,
    ) -> None:
        state_key = self._state_key(run_id)
        encoded = {key: self._encode(value) for key, value in state.items()}
        encoded.setdefault("run_id", self._encode(str(run_id)))
        encoded.setdefault("cancel_requested", self._encode(False))
        encoded.setdefault("lease_generation", self._encode(0))
        encoded["updated_at"] = self._encode(datetime.now(timezone.utc).isoformat())
        async with self._client.pipeline(transaction=False) as pipe:
            pipe.hset(state_key, mapping=encoded)
            pipe.expire(state_key, ttl_seconds)
            await pipe.execute()

    async def get(self, run_id: UUID) -> dict[str, Any] | None:
        raw = await self._client.hgetall(self._state_key(run_id))
        if not raw:
            return None
        return {str(key): self._decode(value) for key, value in raw.items()}

    async def update(self, run_id: UUID, values: dict[str, Any]) -> None:
        if not values:
            return
        mapping = {key: self._encode(value) for key, value in values.items()}
        mapping["updated_at"] = self._encode(datetime.now(timezone.utc).isoformat())
        await self._client.hset(self._state_key(run_id), mapping=mapping)

    async def append_event(
        self,
        run_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        *,
        maxlen: int = 2000,
    ) -> str | None:
        event_id = await self._client.xadd(
            self._events_key(run_id),
            {
                "type": event_type,
                "payload": self._encode(payload),
                "at": datetime.now(timezone.utc).isoformat(),
            },
            maxlen=maxlen,
            approximate=True,
        )
        return str(event_id) if event_id is not None else None

    async def request_cancel(self, run_id: UUID) -> None:
        await self.update(run_id, {"cancel_requested": True})

    async def is_cancel_requested(self, run_id: UUID) -> bool:
        value = await self._client.hget(self._state_key(run_id), "cancel_requested")
        return bool(self._decode(value)) if value is not None else False

    async def acquire_lease(
        self,
        run_id: UUID,
        *,
        worker_id: str,
        ttl_seconds: int,
    ) -> ExecutionLease | None:
        generation = await self._client.eval(
            _ACQUIRE_LEASE_SCRIPT,
            2,
            self._lease_key(run_id),
            self._state_key(run_id),
            worker_id,
            int(ttl_seconds * 1000),
        )
        if not generation:
            return None
        return ExecutionLease(owner=worker_id, generation=int(generation))

    async def renew_lease(
        self,
        run_id: UUID,
        *,
        worker_id: str,
        ttl_seconds: int,
    ) -> bool:
        renewed = await self._client.eval(
            _RENEW_LEASE_SCRIPT,
            2,
            self._lease_key(run_id),
            self._state_key(run_id),
            worker_id,
            int(ttl_seconds * 1000),
        )
        return bool(renewed)

    async def increment(
        self,
        run_id: UUID,
        field: str,
        *,
        amount: int = 1,
    ) -> int:
        return int(await self._client.hincrby(self._state_key(run_id), field, amount))

    async def expire(self, run_id: UUID, *, ttl_seconds: int) -> None:
        async with self._client.pipeline(transaction=False) as pipe:
            pipe.expire(self._state_key(run_id), ttl_seconds)
            pipe.expire(self._events_key(run_id), ttl_seconds)
            pipe.expire(self._lease_key(run_id), ttl_seconds)
            await pipe.execute()

    async def delete(self, run_id: UUID) -> None:
        await self._client.delete(
            self._state_key(run_id),
            self._events_key(run_id),
            self._lease_key(run_id),
        )
