from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.application.runtime import (
    AgentInvocationResult,
    NetworkExecutionSnapshot,
)
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from modules.network.infra.workers.execution_worker import NetworkExecutionProcessor
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


def _execution(*, status: str = "queued") -> NetworkExecutionSnapshot:
    return NetworkExecutionSnapshot(
        id=uuid4(),
        network_id=uuid4(),
        network_version_id=None,
        network_session_id=uuid4(),
        project_id=uuid4(),
        input_message="network input",
        draft_revision=1,
        definition_snapshot={"nodes": [], "edges": []},
        resolved_bindings_snapshot={},
        status=status,
    )


@pytest.mark.asyncio
async def test_network_cancellation_preserves_completed_children_and_only_cancels_in_flight_invocations() -> None:
    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    execution = _execution()
    await store.initialize(execution, ttl_seconds=3600)

    completed = await store.start_invocation(
        execution=execution,
        node_id=uuid4(),
        agent_id=uuid4(),
        depth=1,
        message="completed child",
        parent_invocation_id=None,
        persist_context=False,
    )
    await store.complete_invocation(
        completed.id,
        result=AgentInvocationResult(
            answer="completed output",
            session_id=None,
            trace_id=uuid4(),
            provider="test",
            model="test-model",
            usage=None,
            tool_calls=[],
            sources=[],
        ),
        persist_context=False,
    )

    running = await store.start_invocation(
        execution=execution,
        node_id=uuid4(),
        agent_id=uuid4(),
        depth=2,
        message="in-flight child",
        parent_invocation_id=completed.id,
        persist_context=False,
    )

    await store.cancel_running_invocations(execution.id)

    by_id = {
        item["id"]: item
        for item in await store.invocations(execution.id)
    }
    assert by_id[str(completed.id)]["status"] == "completed"
    assert by_id[str(completed.id)]["output_message"] == "completed output"
    assert by_id[str(running.id)]["status"] == "cancelled"
    assert by_id[str(running.id)]["error"] is None
    assert by_id[str(running.id)]["completed_at"] is not None


class _Loader:
    def __init__(self, execution) -> None:
        self.execution = execution
        self.load_calls = 0

    async def load(self, _execution_id):
        self.load_calls += 1
        return SimpleNamespace(
            execution=self.execution,
            version=SimpleNamespace(id=uuid4()),
            agent_contexts={},
        )


class _PendingCancellationStore:
    def __init__(self) -> None:
        self.initialized = []
        self.cancel_requested = []
        self.persisted = []
        self.lease_calls = 0

    async def initialize(self, execution, *, ttl_seconds, agent_contexts=None) -> None:
        self.initialized.append((execution.id, ttl_seconds, agent_contexts or {}))

    async def request_cancel(self, execution_id) -> None:
        self.cancel_requested.append(execution_id)

    async def mark_persisted(self, execution_id, *, status) -> None:
        self.persisted.append((execution_id, status))

    async def snapshot(self, _execution_id):
        return {"status": "running"}

    async def acquire_lease(self, *_args, **_kwargs):
        self.lease_calls += 1
        return None


@pytest.mark.asyncio
async def test_network_worker_restores_pending_durable_cancellation_before_acquiring_execution_lease() -> None:
    execution = SimpleNamespace(
        id=uuid4(),
        status="cancel_requested",
        draft_revision=1,
        definition_snapshot={"nodes": [], "edges": []},
        resolved_bindings_snapshot={},
    )
    store = _PendingCancellationStore()
    processor = object.__new__(NetworkExecutionProcessor)
    processor._loader = _Loader(execution)
    processor._store = store
    processor._finalizer = SimpleNamespace()
    processor._lease_ttl_seconds = 60
    processor._heartbeat_seconds = 5
    processor._worker_id = "test-worker"
    processor._agent_invoker = SimpleNamespace()

    await processor.process(execution.id)

    assert store.initialized
    assert store.cancel_requested == [execution.id]
    assert store.persisted == []
    assert store.lease_calls == 1


@pytest.mark.asyncio
async def test_network_worker_does_not_restart_durably_cancelled_execution() -> None:
    execution = SimpleNamespace(
        id=uuid4(),
        status="cancelled",
        draft_revision=1,
        definition_snapshot={"nodes": [], "edges": []},
        resolved_bindings_snapshot={},
    )
    store = _PendingCancellationStore()
    processor = object.__new__(NetworkExecutionProcessor)
    processor._loader = _Loader(execution)
    processor._store = store
    processor._finalizer = SimpleNamespace()
    processor._lease_ttl_seconds = 60
    processor._heartbeat_seconds = 5
    processor._worker_id = "test-worker"
    processor._agent_invoker = SimpleNamespace()

    await processor.process(execution.id)

    assert store.initialized == []
    assert store.cancel_requested == []
    assert store.persisted == []
    assert store.lease_calls == 0
