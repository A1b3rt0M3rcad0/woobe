from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from shared.contracts.run_event_buffer import (
    BufferedRunEvent,
    RunEventAppendReceipt,
    RunEventBufferPort,
)
from shared.runtime.event_schema import new_event_id, sanitize_run_event_value, validate_event_type

_APPEND_SCRIPT = """
local state_key = KEYS[1]
local stream_key = KEYS[2]
local sequence = redis.call('HINCRBY', state_key, 'journal_sequence', 1)
local cursor = redis.call(
  'XADD', stream_key, '*',
  'run_id', ARGV[1],
  'run_kind', ARGV[2],
  'sequence', sequence,
  'event_id', ARGV[3],
  'event_type', ARGV[4],
  'occurred_at', ARGV[5],
  'schema_version', ARGV[6],
  'storage_version', ARGV[7],
  'metadata', ARGV[8],
  'payload', ARGV[9],
  'session_id', ARGV[10]
)
redis.call('HSET', state_key, 'last_buffer_cursor', cursor, 'updated_at', ARGV[5])
return {cursor, sequence}
"""

_ENSURE_SEQUENCE_SCRIPT = """
local state_key = KEYS[1]
local requested = tonumber(ARGV[1])
local current = tonumber(redis.call('HGET', state_key, 'journal_sequence') or '0')
if current < requested then
  redis.call('HSET', state_key, 'journal_sequence', requested)
  return requested
end
return current
"""


class RedisRunEventBuffer(RunEventBufferPort):
    """Untrimmed Redis Stream used only for Redis -> Mongo delivery."""

    def __init__(
        self,
        client: Redis,
        *,
        stream_key: str = "woobe:runtime:journal:persistence",
        dead_letter_key: str = "woobe:runtime:journal:dead",
        state_prefix: str = "woobe:runtime:journal:run",
    ) -> None:
        self._client = client
        self._stream_key = stream_key
        self._dead_letter_key = dead_letter_key
        self._state_prefix = state_prefix.rstrip(":")

    def _state_key(self, run_id: UUID) -> str:
        return f"{self._state_prefix}:{run_id}"

    @staticmethod
    def _encode(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def _decode(value: Any, default: Any) -> Any:
        if value is None:
            return default
        try:
            return json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return default

    @classmethod
    def _event(cls, cursor: Any, fields: dict[str, Any]) -> BufferedRunEvent:
        metadata = cls._decode(fields.get("metadata"), {})
        payload = cls._decode(fields.get("payload"), {})
        session_id = fields.get("session_id") or metadata.get("session_id") or metadata.get("network_session_id")
        return BufferedRunEvent(
            cursor=str(cursor),
            session_id=UUID(str(session_id)) if session_id else None,
            run_id=UUID(str(fields["run_id"])),
            run_kind=str(fields["run_kind"]),
            sequence=int(fields["sequence"]),
            event_id=str(fields["event_id"]),
            event_type=str(fields["event_type"]),
            occurred_at=str(fields["occurred_at"]),
            schema_version=int(fields.get("schema_version") or 1),
            storage_version=str(fields.get("storage_version") or "event_journal_v1"),
            metadata=metadata if isinstance(metadata, dict) else {},
            payload=payload if isinstance(payload, dict) else {"value": payload},
        )

    async def append(
        self,
        *,
        run_id: UUID,
        session_id: UUID,
        run_kind: str,
        event_type: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        schema_version: int = 1,
        storage_version: str = "event_journal_v1",
    ) -> RunEventAppendReceipt:
        if session_id is None:
            raise ValueError("Durable Run event requires a Session")
        normalized_type = validate_event_type(event_type)
        occurred_at = datetime.now(timezone.utc).isoformat()
        result = await self._client.eval(
            _APPEND_SCRIPT,
            2,
            self._state_key(run_id),
            self._stream_key,
            str(run_id),
            run_kind,
            new_event_id(),
            normalized_type,
            occurred_at,
            int(schema_version),
            storage_version,
            self._encode(sanitize_run_event_value(metadata or {})),
            self._encode(sanitize_run_event_value(payload)),
            str(session_id),
        )
        if not result:
            raise RuntimeError(f"Redis did not append durable Run event for {run_id}")
        return RunEventAppendReceipt(
            run_id=run_id,
            sequence=int(result[1]),
            cursor=str(result[0]),
            occurred_at=occurred_at,
        )

    async def ensure_sequence_at_least(self, run_id: UUID, sequence: int) -> int:
        """Reconcile the Redis allocator with an already durable Mongo prefix.

        Recovery may rebuild Redis hot state after the journal already contains events.
        Moving this counter backwards would reuse ``run_id + sequence`` and corrupt the
        logical ordering, so reconciliation is monotonic and happens before a new Attempt.
        """

        return int(
            await self._client.eval(
                _ENSURE_SEQUENCE_SCRIPT,
                1,
                self._state_key(run_id),
                max(0, int(sequence)),
            )
        )

    async def ensure_consumer_group(self, group: str) -> None:
        try:
            await self._client.xgroup_create(
                self._stream_key,
                group,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def read_group(
        self,
        *,
        group: str,
        consumer: str,
        count: int,
        block_ms: int,
    ) -> list[BufferedRunEvent]:
        rows = await self._client.xreadgroup(
            group,
            consumer,
            {self._stream_key: ">"},
            count=max(1, int(count)),
            block=max(0, int(block_ms)),
        )
        return self._rows(rows)

    async def claim_idle(
        self,
        *,
        group: str,
        consumer: str,
        min_idle_ms: int,
        count: int,
    ) -> list[BufferedRunEvent]:
        result = await self._client.xautoclaim(
            self._stream_key,
            group,
            consumer,
            min_idle_time=max(1, int(min_idle_ms)),
            start_id="0-0",
            count=max(1, int(count)),
        )
        entries = result[1] if result and len(result) > 1 else []
        return [self._event(cursor, fields) for cursor, fields in entries]

    def _rows(self, rows: Any) -> list[BufferedRunEvent]:
        events: list[BufferedRunEvent] = []
        for _stream, entries in rows or []:
            for cursor, fields in entries:
                events.append(self._event(cursor, fields))
        return events

    async def ack(self, group: str, cursors: list[str]) -> None:
        if cursors:
            await self._client.xack(self._stream_key, group, *cursors)

    async def dead_letter(self, event: BufferedRunEvent, *, reason: str) -> None:
        await self._client.xadd(
            self._dead_letter_key,
            {
                "source_cursor": event.cursor,
                "run_id": str(event.run_id),
                "sequence": str(event.sequence),
                "event_type": event.event_type,
                "reason": reason[:2000],
                "occurred_at": datetime.now(timezone.utc).isoformat(),
            },
        )
