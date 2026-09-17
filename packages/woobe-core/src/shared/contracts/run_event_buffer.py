from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RunEventAppendReceipt:
    run_id: UUID
    sequence: int
    cursor: str
    occurred_at: str


@dataclass(frozen=True, slots=True)
class BufferedRunEvent:
    cursor: str
    run_id: UUID
    run_kind: str
    sequence: int
    event_id: str
    event_type: str
    occurred_at: str
    schema_version: int
    storage_version: str
    metadata: dict[str, Any]
    payload: dict[str, Any]
    session_id: UUID | None = None  # None only for pre-v2 journal records.



class RunEventBufferPort(Protocol):
    """Reliable ingress between runtime execution and durable Run persistence."""

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
    ) -> RunEventAppendReceipt: ...

    async def ensure_sequence_at_least(self, run_id: UUID, sequence: int) -> int: ...

    async def ensure_consumer_group(self, group: str) -> None: ...

    async def read_group(
        self,
        *,
        group: str,
        consumer: str,
        count: int,
        block_ms: int,
    ) -> list[BufferedRunEvent]: ...

    async def claim_idle(
        self,
        *,
        group: str,
        consumer: str,
        min_idle_ms: int,
        count: int,
    ) -> list[BufferedRunEvent]: ...

    async def ack(self, group: str, cursors: list[str]) -> None: ...

    async def dead_letter(self, event: BufferedRunEvent, *, reason: str) -> None: ...
