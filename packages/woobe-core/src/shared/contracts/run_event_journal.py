from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DurableRunEvent:
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


@dataclass(frozen=True, slots=True)
class RunJournalState:
    run_id: UUID
    run_kind: str
    storage_version: str
    durable_sequence: int = 0
    checkpoint_sequence: int = 0
    terminal_sequence: int | None = None
    terminal_status: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class RunCheckpoint:
    run_id: UUID
    through_sequence: int
    attempt: int
    state: dict[str, Any]
    updated_at: str


class RunEventJournalPort(Protocol):
    """Durable append-only execution journal and checkpoint store."""

    async def ensure_indexes(self) -> None: ...

    async def write_batch(self, events: Sequence[DurableRunEvent]) -> None: ...

    async def list_events(
        self,
        run_id: UUID,
        *,
        after_sequence: int = 0,
        through_sequence: int | None = None,
        limit: int = 5000,
    ) -> list[DurableRunEvent]: ...

    async def get_state(self, run_id: UUID) -> RunJournalState | None: ...

    async def advance_durable_sequence(
        self,
        run_id: UUID,
        *,
        run_kind: str,
        storage_version: str,
    ) -> RunJournalState: ...

    async def upsert_checkpoint(self, checkpoint: RunCheckpoint) -> None: ...

    async def latest_checkpoint(self, run_id: UUID) -> RunCheckpoint | None: ...

    async def close(self) -> None: ...
