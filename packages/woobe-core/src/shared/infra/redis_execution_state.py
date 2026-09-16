from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from redis.asyncio import Redis

from shared.contracts.execution_state import ExecutionEvent, ExecutionLease, ExecutionStateStore


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

_APPEND_EVENT_SCRIPT = """
local state_key = KEYS[1]
local events_key = KEYS[2]
local event_type = ARGV[1]
local payload = ARGV[2]
local occurred_at = ARGV[3]
local maxlen = tonumber(ARGV[4])
local expected = tonumber(redis.call('HGET', state_key, 'event_sequence') or '0') + 1
local explicit = tonumber(ARGV[6])
if explicit and explicit ~= expected then
  return redis.error_reply('Runtime sequence must be ' .. expected .. ', received ' .. explicit)
end
local sequence = expected
local cursor = redis.call(
  'XADD', events_key, 'MAXLEN', '~', maxlen, '*',
  'event_id', ARGV[5],
  'sequence', sequence,
  'type', event_type,
  'payload', payload,
  'at', occurred_at
)
redis.call('HSET', state_key, 'event_sequence', sequence, 'last_event_cursor', cursor, 'updated_at', occurred_at)
local state_ttl_ms = redis.call('PTTL', state_key)
if state_ttl_ms > 0 then
  redis.call('PEXPIRE', events_key, state_ttl_ms)
end
return {cursor, sequence}
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

    @classmethod
    def _event(cls, cursor: str, fields: dict[str, str]) -> ExecutionEvent:
        payload = cls._decode(fields.get("payload", "{}"))
        return ExecutionEvent(
            event_id=str(fields.get("event_id") or ""),
            sequence=int(fields.get("sequence") or 0),
            cursor=str(cursor),
            event_type=str(fields.get("type") or "runtime.event"),
            payload=payload if isinstance(payload, dict) else {"value": payload},
            occurred_at=str(fields.get("at") or ""),
        )

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
        encoded.setdefault("event_sequence", self._encode(0))
        encoded.setdefault("last_event_cursor", self._encode("0-0"))
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
        event_id: str | None = None,
        sequence: int | None = None,
        occurred_at: str | None = None,
    ) -> str | None:
        if sequence is not None and (isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1):
            raise ValueError("Explicit runtime sequence must be a positive integer")
        occurred_at = occurred_at or datetime.now(timezone.utc).isoformat()
        result = await self._client.eval(
            _APPEND_EVENT_SCRIPT,
            2,
            self._state_key(run_id),
            self._events_key(run_id),
            event_type,
            self._encode(payload),
            occurred_at,
            max(1, int(maxlen)),
            event_id or str(uuid4()),
            sequence if sequence is not None else "",
        )
        if not result:
            return None
        cursor = result[0]
        return str(cursor) if cursor is not None else None

    async def list_events_after(
        self,
        run_id: UUID,
        sequence: int,
        *,
        through_sequence: int | None = None,
        limit: int = 2000,
    ) -> list[ExecutionEvent]:
        rows = await self._client.xrange(
            self._events_key(run_id),
            min="-",
            max="+",
            count=max(1, int(limit)),
        )
        events: list[ExecutionEvent] = []
        for cursor, fields in rows:
            event = self._event(str(cursor), fields)
            if event.sequence <= sequence:
                continue
            if through_sequence is not None and event.sequence > through_sequence:
                break
            events.append(event)
        return events

    async def read_events_after_cursor(
        self,
        run_id: UUID,
        cursor: str,
        *,
        block_ms: int = 1000,
        limit: int = 100,
    ) -> list[ExecutionEvent]:
        rows = await self._client.xread(
            {self._events_key(run_id): cursor or "0-0"},
            count=max(1, int(limit)),
            block=max(0, int(block_ms)),
        )
        if not rows:
            return []
        events: list[ExecutionEvent] = []
        for _stream_name, entries in rows:
            for event_cursor, fields in entries:
                events.append(self._event(str(event_cursor), fields))
        return events

    async def first_event_sequence(self, run_id: UUID) -> int | None:
        rows = await self._client.xrange(
            self._events_key(run_id),
            min="-",
            max="+",
            count=1,
        )
        if not rows:
            return None
        _cursor, fields = rows[0]
        raw_sequence = fields.get("sequence")
        return int(raw_sequence) if raw_sequence is not None else None

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
