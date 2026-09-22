from __future__ import annotations

import json
from uuid import uuid4

import pytest

_SESSION_ID = uuid4()

from shared.contracts.run_event_journal import DurableRunEvent
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.infra.in_memory_run_event_journal import InMemoryRunEventJournal
from shared.runtime import RunReference, RuntimeObserver


def _event(
    *,
    run_id,
    run_kind: str,
    sequence: int,
    event_type: str,
    payload: dict | None = None,
) -> DurableRunEvent:
    return DurableRunEvent(
        run_id=run_id,
        session_id=_SESSION_ID,
        run_kind=run_kind,
        sequence=sequence,
        event_id=f"event-{sequence}",
        event_type=event_type,
        occurred_at=f"2026-09-10T18:00:0{sequence}+00:00",
        schema_version=1,
        storage_version="event_journal_v1",
        metadata={"project_id": str(uuid4()), "visibility": "internal"},
        payload=payload or {},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("run_kind", ["agent", "network"])
async def test_observer_replays_terminal_state_from_journal_without_hot_redis(
    run_kind: str,
) -> None:
    run_id = uuid4()
    store = InMemoryExecutionStateStore()
    journal = InMemoryRunEventJournal()
    await journal.write_batch(
        [
            _event(
                run_id=run_id,
                run_kind=run_kind,
                sequence=1,
                event_type="run.attempt.started",
            ),
            _event(
                run_id=run_id,
                run_kind=run_kind,
                sequence=2,
                event_type="output.delta.batch",
                payload={"content": "journal answer"},
            ),
            _event(
                run_id=run_id,
                run_kind=run_kind,
                sequence=3,
                event_type="run.completed",
                payload={"output": "journal answer", "answer": "journal answer"},
            ),
        ]
    )
    observer = RuntimeObserver(store, journal=journal, local_poll_seconds=0.01)

    async def relational_fallback():
        return {"status": "running", "output": "", "result": None}

    run = RunReference.agent(run_id) if run_kind == "agent" else RunReference.network(run_id)
    stream = observer.observe(run, durable_fallback=relational_fallback)
    state = await anext(stream)

    assert state.event_type == "run.state"
    assert state.sequence == 0
    assert state.session_id == _SESSION_ID
    assert state.data["sequence"] is None
    assert state.data["status"] == "completed"
    assert state.data["output"] == "journal answer"
    assert state.data["realtime_available"] is False
    assert state.data["durable_source"] == "mongodb_journal"
    assert state.data["journal_durable_sequence"] == 3

    with pytest.raises(StopAsyncIteration):
        await anext(stream)


@pytest.mark.asyncio
async def test_observer_rebuilds_partial_agent_output_from_journal_without_hot_redis() -> None:
    run_id = uuid4()
    journal = InMemoryRunEventJournal()
    await journal.write_batch(
        [
            _event(
                run_id=run_id,
                run_kind="agent",
                sequence=1,
                event_type="run.attempt.started",
            ),
            _event(
                run_id=run_id,
                run_kind="agent",
                sequence=2,
                event_type="output.delta.batch",
                payload={"content": "Hello "},
            ),
            _event(
                run_id=run_id,
                run_kind="agent",
                sequence=3,
                event_type="output.delta.batch",
                payload={"content": "world"},
            ),
        ]
    )
    observer = RuntimeObserver(
        InMemoryExecutionStateStore(),
        journal=journal,
        local_poll_seconds=0.01,
    )

    async def relational_fallback():
        return {"status": "running", "output": "", "result": None}

    state, cursor = await observer.current_state(
        RunReference.agent(run_id),
        durable_fallback=relational_fallback,
    )

    assert cursor is None
    assert state["status"] == "running"
    assert state["output"] == "Hello world"
    assert state["sequence"] is None
    assert state["realtime_available"] is False
    assert state["durable_source"] == "mongodb_journal"
    assert state["journal_durable_sequence"] == 3


@pytest.mark.asyncio
async def test_network_observer_replays_completed_intermediate_message_from_journal() -> None:
    run_id = uuid4()
    message_id = str(uuid4())
    journal = InMemoryRunEventJournal()
    await journal.write_batch(
        [
            _event(
                run_id=run_id,
                run_kind="network",
                sequence=1,
                event_type="run.attempt.started",
            ),
            _event(
                run_id=run_id,
                run_kind="network",
                sequence=2,
                event_type="assistant.message.completed",
                payload={
                    "message_id": message_id,
                    "content": "I found a likely cause and will verify it.",
                    "phase": "verification",
                    "output_mode": "intermediate",
                    "provider": "custom",
                    "model": "test-model",
                    "partial": False,
                    "completed_at": "2026-09-10T18:00:02+00:00",
                },
            ),
        ]
    )
    observer = RuntimeObserver(
        InMemoryExecutionStateStore(),
        journal=journal,
        local_poll_seconds=0.01,
    )

    async def relational_fallback():
        return {"status": "running", "output": "", "result": None}

    state, cursor = await observer.current_state(
        RunReference.network(run_id),
        durable_fallback=relational_fallback,
    )

    assert cursor is None
    assert state["status"] == "running"
    assert state["output"] == ""
    assert state["realtime_available"] is False
    assert state["durable_source"] == "mongodb_journal"
    assert state["journal_durable_sequence"] == 2
    assert state["messages"] == [
        {
            "message_id": message_id,
            "content": "I found a likely cause and will verify it.",
            "phase": "verification",
            "output_mode": "intermediate",
            "provider": "custom",
            "model": "test-model",
            "partial": False,
            "completed_at": "2026-09-10T18:00:02+00:00",
            "status": "completed",
        }
    ]


@pytest.mark.asyncio
async def test_journal_observer_does_not_expose_internal_event_payloads() -> None:
    run_id = uuid4()
    journal = InMemoryRunEventJournal()
    await journal.write_batch(
        [
            _event(
                run_id=run_id,
                run_kind="agent",
                sequence=1,
                event_type="run.attempt.started",
                payload={"input_message": "private-input"},
            ),
            _event(
                run_id=run_id,
                run_kind="agent",
                sequence=2,
                event_type="tool.call.started",
                payload={
                    "tool_call_id": "tool-1",
                    "tool_name": "lookup",
                    "input": {"secret": "private-tool-input"},
                },
            ),
            _event(
                run_id=run_id,
                run_kind="agent",
                sequence=3,
                event_type="run.failed",
                payload={
                    "failure_code": "runtime_error",
                    "error": "private-provider-error",
                },
            ),
        ]
    )
    observer = RuntimeObserver(
        InMemoryExecutionStateStore(),
        journal=journal,
        local_poll_seconds=0.01,
    )

    async def relational_fallback():
        return {"status": "running", "output": ""}

    stream = observer.observe(
        RunReference.agent(run_id),
        durable_fallback=relational_fallback,
    )
    state = await anext(stream)
    encoded = json.dumps(state.data, default=str)

    assert state.data["status"] == "failed"
    assert "private-input" not in encoded
    assert "private-tool-input" not in encoded
    assert "private-provider-error" not in encoded
    await stream.aclose()
