from __future__ import annotations

import asyncio
from uuid import UUID

from shared.contracts.run_event_journal import RunEventJournalPort


class RunDurabilityTimeout(RuntimeError):
    pass


class RunDurabilityBarrier:
    """Wait until Mongo has a contiguous durable prefix through ``sequence``."""

    def __init__(
        self,
        journal: RunEventJournalPort,
        *,
        timeout_seconds: float = 5.0,
        poll_interval_seconds: float = 0.025,
    ) -> None:
        self._journal = journal
        self._timeout_seconds = max(0.1, float(timeout_seconds))
        self._poll_interval_seconds = max(0.005, float(poll_interval_seconds))

    async def wait_until(self, run_id: UUID, sequence: int) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._timeout_seconds
        while True:
            state = await self._journal.get_state(run_id)
            if state is not None and state.durable_sequence >= sequence:
                return
            remaining = deadline - loop.time()
            if remaining <= 0:
                durable = state.durable_sequence if state is not None else 0
                raise RunDurabilityTimeout(
                    f"Run {run_id} journal durability timed out at sequence "
                    f"{durable}; required {sequence}"
                )
            await asyncio.sleep(min(self._poll_interval_seconds, remaining))
