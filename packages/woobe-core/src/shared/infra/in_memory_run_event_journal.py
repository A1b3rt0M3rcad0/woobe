from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from shared.contracts.run_event_journal import (
    DurableRunEvent,
    RunCheckpoint,
    RunEventJournalPort,
    RunJournalState,
)
from shared.runtime.event_schema import CHECKPOINT_EVENT_TYPE, TERMINAL_EVENT_TYPES


class InMemoryRunEventJournal(RunEventJournalPort):
    def __init__(self) -> None:
        self.events: dict[UUID, dict[int, DurableRunEvent]] = {}
        self.states: dict[UUID, RunJournalState] = {}
        self.checkpoints: dict[UUID, RunCheckpoint] = {}

    async def ensure_indexes(self) -> None:
        return None

    async def write_batch(self, events: Sequence[DurableRunEvent]) -> None:
        for event in events:
            self.events.setdefault(event.run_id, {})[event.sequence] = event
            if event.event_type == CHECKPOINT_EVENT_TYPE:
                raw = event.payload.get("state")
                if isinstance(raw, dict):
                    await self.upsert_checkpoint(
                        RunCheckpoint(
                            run_id=event.run_id,
                            through_sequence=event.sequence,
                            attempt=int(event.payload.get("attempt") or 1),
                            state=dict(raw),
                            updated_at=event.occurred_at,
                        )
                    )
        for run_id in {event.run_id for event in events}:
            sample = next(event for event in events if event.run_id == run_id)
            await self.advance_durable_sequence(
                run_id,
                run_kind=sample.run_kind,
                storage_version=sample.storage_version,
            )

    async def list_events(
        self,
        run_id: UUID,
        *,
        after_sequence: int = 0,
        through_sequence: int | None = None,
        limit: int = 5000,
    ) -> list[DurableRunEvent]:
        values = [
            event
            for sequence, event in sorted(self.events.get(run_id, {}).items())
            if sequence > after_sequence
            and (through_sequence is None or sequence <= through_sequence)
        ]
        return values[: max(1, int(limit))]

    async def get_state(self, run_id: UUID) -> RunJournalState | None:
        return self.states.get(run_id)

    async def advance_durable_sequence(
        self,
        run_id: UUID,
        *,
        run_kind: str,
        storage_version: str,
    ) -> RunJournalState:
        previous = self.states.get(run_id)
        durable = previous.durable_sequence if previous else 0
        mapping = self.events.get(run_id, {})
        while durable + 1 in mapping:
            durable += 1
        terminal_sequence = previous.terminal_sequence if previous else None
        terminal_status = previous.terminal_status if previous else None
        checkpoint_sequence = previous.checkpoint_sequence if previous else 0
        for sequence in range(1, durable + 1):
            event = mapping.get(sequence)
            if event is None:
                continue
            if event.event_type == CHECKPOINT_EVENT_TYPE:
                checkpoint_sequence = max(checkpoint_sequence, sequence)
            status = TERMINAL_EVENT_TYPES.get(event.event_type)
            if status is not None:
                terminal_sequence = sequence
                terminal_status = status
        state = RunJournalState(
            run_id=run_id,
            run_kind=run_kind,
            storage_version=storage_version,
            durable_sequence=durable,
            checkpoint_sequence=checkpoint_sequence,
            terminal_sequence=terminal_sequence,
            terminal_status=terminal_status,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self.states[run_id] = state
        return state

    async def upsert_checkpoint(self, checkpoint: RunCheckpoint) -> None:
        current = self.checkpoints.get(checkpoint.run_id)
        if current is None or checkpoint.through_sequence >= current.through_sequence:
            self.checkpoints[checkpoint.run_id] = checkpoint

    async def latest_checkpoint(self, run_id: UUID) -> RunCheckpoint | None:
        return self.checkpoints.get(run_id)

    async def close(self) -> None:
        return None
