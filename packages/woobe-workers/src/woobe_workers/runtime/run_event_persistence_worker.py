from __future__ import annotations

import asyncio
import logging
import socket
from collections.abc import Sequence
from uuid import UUID

from shared.contracts.run_event_buffer import BufferedRunEvent, RunEventBufferPort
from shared.contracts.run_event_journal import DurableRunEvent, RunEventJournalPort
from shared.contracts.run_event_projector import RunEventProjectorPort
from shared.runtime.event_schema import buffered_to_durable

logger = logging.getLogger(__name__)


class RunEventPersistenceWorker:
    """Drain the reliable Redis Run journal ingress into MongoDB and read models.

    Redis delivery is at-least-once. Mongo writes are idempotent by
    ``run_id + sequence``. PostgreSQL projection happens only through the Mongo
    contiguous durable watermark, and Redis entries are acknowledged only after
    both journal persistence and configured projections succeed.
    """

    long_lived = True

    def __init__(
        self,
        *,
        buffer: RunEventBufferPort,
        journal: RunEventJournalPort,
        consumer_group: str,
        projector: RunEventProjectorPort | None = None,
        batch_size: int = 250,
        flush_interval_ms: int = 200,
        claim_idle_seconds: int = 30,
        consumer_name: str | None = None,
    ) -> None:
        self._buffer = buffer
        self._journal = journal
        self._projector = projector
        self._consumer_group = consumer_group
        self._batch_size = max(1, int(batch_size))
        self._flush_interval_ms = max(10, int(flush_interval_ms))
        self._claim_idle_ms = max(1000, int(claim_idle_seconds) * 1000)
        self._consumer_name = consumer_name or f"{socket.gethostname()}-{id(self):x}"
        self._projected_hint: dict[UUID, int] = {}

    @staticmethod
    def _durable_event(event: BufferedRunEvent) -> DurableRunEvent:
        return buffered_to_durable(event)

    async def _persist_batch(self, events: Sequence[BufferedRunEvent]) -> None:
        if not events:
            return

        await self._journal.write_batch([self._durable_event(event) for event in events])

        samples: dict[UUID, BufferedRunEvent] = {}
        for event in events:
            samples.setdefault(event.run_id, event)

        durable_sequences: dict[UUID, int] = {}
        for run_id, sample in samples.items():
            state = await self._journal.advance_durable_sequence(
                run_id,
                run_kind=sample.run_kind,
                storage_version=sample.storage_version,
            )
            durable_sequences[run_id] = state.durable_sequence

            if self._projector is not None:
                after_sequence = self._projected_hint.get(run_id, 0)
                if state.durable_sequence > after_sequence:
                    durable_events = await self._journal.list_events(
                        run_id,
                        after_sequence=after_sequence,
                        through_sequence=state.durable_sequence,
                    )
                    if durable_events:
                        await self._projector.project(durable_events)
                    self._projected_hint[run_id] = state.durable_sequence

        ackable = [
            event.cursor
            for event in events
            if event.sequence <= durable_sequences.get(event.run_id, 0)
        ]
        await self._buffer.ack(self._consumer_group, ackable)

    async def run(self) -> None:
        await self._journal.ensure_indexes()
        await self._buffer.ensure_consumer_group(self._consumer_group)

        retry_delay = max(0.05, self._flush_interval_ms / 1000.0)
        while True:
            try:
                claimed = await self._buffer.claim_idle(
                    group=self._consumer_group,
                    consumer=self._consumer_name,
                    min_idle_ms=self._claim_idle_ms,
                    count=self._batch_size,
                )
                if claimed:
                    await self._persist_batch(claimed)

                fresh = await self._buffer.read_group(
                    group=self._consumer_group,
                    consumer=self._consumer_name,
                    count=self._batch_size,
                    block_ms=self._flush_interval_ms,
                )
                if fresh:
                    await self._persist_batch(fresh)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Do not ACK on journal/watermark/projection failure. Pending Redis
                # entries are reclaimed and replayed idempotently.
                logger.exception("Run event persistence batch failed")
                await asyncio.sleep(retry_delay)
