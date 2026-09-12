from __future__ import annotations

from typing import Protocol, Sequence

from shared.contracts.run_event_journal import DurableRunEvent


class RunEventProjectorPort(Protocol):
    """Idempotent durable-event to read-model projection boundary."""

    async def project(self, events: Sequence[DurableRunEvent]) -> None: ...
