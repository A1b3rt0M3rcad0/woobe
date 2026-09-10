from __future__ import annotations

from uuid import uuid4

import pytest

from modules.network.application.runtime import (
    AgentInvocationResult,
    NetworkExecutionSnapshot,
)
from modules.network.infra.runtime.journal_store import JournaledRedisNetworkExecutionStore
from shared.contracts.run_event_buffer import RunEventAppendReceipt
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


class FakeBuffer:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.sequence = 0

    async def append(self, **kwargs):
        self.sequence += 1
        self.events.append({"sequence": self.sequence, **kwargs})
        return RunEventAppendReceipt(
            run_id=kwargs["run_id"],
            sequence=self.sequence,
            cursor=f"{self.sequence}-0",
            occurred_at="2026-09-10T00:00:00+00:00",
        )


class FakeBarrier:
    def __init__(self) -> None:
        self.waits: list[int] = []

    async def wait_until(self, run_id, sequence: int) -> None:
        self.waits.append(sequence)


class FakeSession:
    def __init__(self, execution) -> None:
        self.execution = execution

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, _model, execution_id):
        return self.execution if self.execution.id == execution_id else None


class FakeSessionFactory:
    def __init__(self, execution) -> None:
        self.execution = execution

    def __call__(self):
        return FakeSession(self.execution)


@pytest.mark.anyio
async def test_network_store_journals_invocation_and_safe_checkpoint() -> None:
    execution_id = uuid4()
    project_id = uuid4()
    network_id = uuid4()
    network_session_id = uuid4()
    node_id = uuid4()
    agent_id = uuid4()
    execution_model = type(
        "Execution",
        (),
        {
            "id": execution_id,
            "storage_version": EVENT_JOURNAL_STORAGE_VERSION,
            "attempt": 1,
            "created_at": None,
        },
    )()
    buffer = FakeBuffer()
    barrier = FakeBarrier()
    store = JournaledRedisNetworkExecutionStore(
        InMemoryExecutionStateStore(),
        session_factory=FakeSessionFactory(execution_model),
        buffer=buffer,
        barrier=barrier,
        output_batch_bytes=1024,
        output_flush_interval_ms=200,
    )
    execution = NetworkExecutionSnapshot(
        id=execution_id,
        network_id=network_id,
        network_version_id=None,
        network_session_id=network_session_id,
        project_id=project_id,
        input_message="hello",
        draft_revision=1,
        definition_snapshot={"root_node_id": str(node_id)},
        resolved_bindings_snapshot={},
        status="queued",
    )

    await store.initialize(execution, ttl_seconds=3600)
    invocation = await store.start_invocation(
        execution=execution,
        node_id=node_id,
        agent_id=agent_id,
        depth=0,
        message="hello",
        parent_invocation_id=None,
        persist_context=False,
    )
    await store.emit(
        execution_id,
        "agent_invocation_started",
        {"label": "root"},
        invocation_id=invocation.id,
    )
    await store.complete_invocation(
        invocation.id,
        result=AgentInvocationResult(answer="done"),
        persist_context=False,
    )
    await store.emit(
        execution_id,
        "agent_invocation_completed",
        {"output": "done"},
        invocation_id=invocation.id,
    )

    assert [item["event_type"] for item in buffer.events] == [
        "run.attempt.started",
        "execution.started",
        "agent.invocation.started",
        "agent.invocation.completed",
        "execution.checkpoint",
    ]
    completed = buffer.events[3]
    assert completed["payload"]["invocation"]["status"] == "completed"
    checkpoint = buffer.events[4]
    assert str(invocation.id) in checkpoint["payload"]["state"]["completed_invocation_ids"]
    assert barrier.waits == [1, 5]


@pytest.mark.anyio
async def test_network_store_keeps_legacy_runs_out_of_journal() -> None:
    execution_id = uuid4()
    execution_model = type(
        "Execution",
        (),
        {
            "id": execution_id,
            "storage_version": "legacy_v1",
            "attempt": 1,
            "created_at": None,
        },
    )()
    buffer = FakeBuffer()
    store = JournaledRedisNetworkExecutionStore(
        InMemoryExecutionStateStore(),
        session_factory=FakeSessionFactory(execution_model),
        buffer=buffer,
        barrier=FakeBarrier(),
    )
    execution = NetworkExecutionSnapshot(
        id=execution_id,
        network_id=uuid4(),
        network_version_id=None,
        network_session_id=uuid4(),
        project_id=uuid4(),
        input_message="legacy",
        draft_revision=1,
        definition_snapshot={},
        resolved_bindings_snapshot={},
        status="queued",
    )

    await store.initialize(execution, ttl_seconds=3600)

    assert buffer.events == []
