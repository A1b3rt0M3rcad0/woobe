from __future__ import annotations

from uuid import uuid4

import pytest

from shared.contracts.run_event_buffer import BufferedRunEvent
from shared.infra.in_memory_run_event_journal import InMemoryRunEventJournal
from woobe_workers.runtime.run_event_persistence_worker import RunEventPersistenceWorker
from woobe_workers.runtime.runner import WorkerRunner


class FakeBuffer:
    def __init__(self) -> None:
        self.acked: list[str] = []

    async def ensure_consumer_group(self, group: str) -> None:
        return None

    async def read_group(self, **_kwargs):
        return []

    async def claim_idle(self, **_kwargs):
        return []

    async def ack(self, group: str, cursors: list[str]) -> None:
        self.acked.extend(cursors)

    async def dead_letter(self, event, *, reason: str) -> None:
        raise AssertionError("valid events must not be dead-lettered")


class FakeProjector:
    def __init__(self) -> None:
        self.calls: list[list[int]] = []

    async def project(self, events) -> None:
        self.calls.append([event.sequence for event in events])


def event(*, run_id, sequence: int, cursor: str) -> BufferedRunEvent:
    return BufferedRunEvent(
        cursor=cursor,
        run_id=run_id,
        run_kind="agent",
        sequence=sequence,
        event_id=f"event-{sequence}",
        event_type="execution.started",
        occurred_at="2026-09-10T00:00:00+00:00",
        schema_version=1,
        storage_version="event_journal_v1",
        metadata={"project_id": str(uuid4())},
        payload={},
    )


@pytest.mark.anyio
async def test_worker_acks_only_events_inside_contiguous_durable_prefix() -> None:
    run_id = uuid4()
    buffer = FakeBuffer()
    journal = InMemoryRunEventJournal()
    worker = RunEventPersistenceWorker(
        buffer=buffer,
        journal=journal,
        consumer_group="test-journal",
        consumer_name="test-worker",
    )

    await worker._persist_batch(
        [
            event(run_id=run_id, sequence=1, cursor="1-0"),
            event(run_id=run_id, sequence=3, cursor="3-0"),
        ]
    )

    state = await journal.get_state(run_id)
    assert state is not None
    assert state.durable_sequence == 1
    assert buffer.acked == ["1-0"]


@pytest.mark.anyio
async def test_worker_replay_is_idempotent_and_advances_durable_prefix() -> None:
    run_id = uuid4()
    buffer = FakeBuffer()
    journal = InMemoryRunEventJournal()
    worker = RunEventPersistenceWorker(
        buffer=buffer,
        journal=journal,
        consumer_group="test-journal",
        consumer_name="test-worker",
    )

    first = event(run_id=run_id, sequence=1, cursor="1-0")
    second = event(run_id=run_id, sequence=2, cursor="2-0")
    await worker._persist_batch([first])
    await worker._persist_batch([first, second])

    persisted = await journal.list_events(run_id)
    state = await journal.get_state(run_id)
    assert [item.sequence for item in persisted] == [1, 2]
    assert state is not None
    assert state.durable_sequence == 2
    assert buffer.acked == ["1-0", "1-0", "2-0"]


@pytest.mark.anyio
async def test_worker_projects_only_contiguous_mongo_history_before_ack() -> None:
    run_id = uuid4()
    buffer = FakeBuffer()
    journal = InMemoryRunEventJournal()
    projector = FakeProjector()
    worker = RunEventPersistenceWorker(
        buffer=buffer,
        journal=journal,
        projector=projector,
        consumer_group="test-journal",
        consumer_name="test-worker",
    )

    await worker._persist_batch(
        [
            event(run_id=run_id, sequence=1, cursor="1-0"),
            event(run_id=run_id, sequence=3, cursor="3-0"),
        ]
    )
    await worker._persist_batch([event(run_id=run_id, sequence=2, cursor="2-0")])

    state = await journal.get_state(run_id)
    assert state is not None
    assert state.durable_sequence == 3
    assert projector.calls == [[1], [2, 3]]
    assert buffer.acked == ["1-0", "2-0"]


def test_run_event_persistence_worker_is_long_lived() -> None:
    worker = RunEventPersistenceWorker(
        buffer=FakeBuffer(),
        journal=InMemoryRunEventJournal(),
        consumer_group="test-journal",
        consumer_name="test-worker",
    )
    runner = WorkerRunner([worker])

    assert runner._classify(worker) == "long-lived"
