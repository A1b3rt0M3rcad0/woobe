from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from modules.network.application.runtime import (
    AgentInvocationResult,
    NetworkExecutionCancelled,
    NetworkExecutionSnapshot,
    NetworkExecutor,
    NetworkVersionSnapshot,
)
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from woobe_workers.consumers.network.execution_worker import NetworkExecutionProcessor
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _DelegatingInvoker:
    def __init__(self, root_agent_id, child_agent_id) -> None:
        self.root_agent_id = root_agent_id
        self.child_agent_id = child_agent_id
        self.child_started = asyncio.Event()
        self.child_interrupted = asyncio.Event()

    async def invoke(self, *, agent_id, internal_tools, **_kwargs):
        if agent_id == self.root_agent_id:
            result = await internal_tools[0].handler({"task": "specialist work"})
            return AgentInvocationResult(answer=str(result))

        assert agent_id == self.child_agent_id
        self.child_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.child_interrupted.set()
            raise


@pytest.mark.asyncio
async def test_cancel_during_delegation_cancels_root_and_child_without_failure_semantics() -> None:
    root_node_id = uuid4()
    child_node_id = uuid4()
    root_agent_id = uuid4()
    child_agent_id = uuid4()
    execution = NetworkExecutionSnapshot(
        id=uuid4(),
        network_id=uuid4(),
        network_version_id=uuid4(),
        network_session_id=uuid4(),
        project_id=uuid4(),
        input_message="delegate this request",
        draft_revision=None,
        definition_snapshot=None,
        resolved_bindings_snapshot=None,
        status="queued",
    )
    version = NetworkVersionSnapshot(
        id=execution.network_version_id,
        kind="release",
        definition={
            "schema_version": 2,
            "root_node_id": str(root_node_id),
            "nodes": [
                {
                    "id": str(root_node_id),
                    "agent_id": str(root_agent_id),
                    "label": "Root",
                    "capability_description": "Coordinates specialists.",
                    "position": {"x": 0, "y": 0},
                    "binding": {"source": "release", "release_id": str(uuid4())},
                },
                {
                    "id": str(child_node_id),
                    "agent_id": str(child_agent_id),
                    "label": "Specialist",
                    "capability_description": "Performs specialist work.",
                    "position": {"x": 300, "y": 0},
                    "binding": {"source": "release", "release_id": str(uuid4())},
                },
            ],
            "edges": [
                {
                    "id": str(uuid4()),
                    "source_node_id": str(root_node_id),
                    "target_node_id": str(child_node_id),
                }
            ],
            "settings": {
                "session_mode": "stateless",
                "max_depth": 4,
                "max_invocations": 16,
                "timeout_seconds": 30,
            },
        },
        resolved_bindings={
            str(root_node_id): {
                "release_id": str(uuid4()),
                "session_mode": "stateless",
            },
            str(child_node_id): {
                "release_id": str(uuid4()),
                "session_mode": "stateless",
            },
        },
    )
    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    await store.initialize(execution, ttl_seconds=3600)
    invoker = _DelegatingInvoker(root_agent_id, child_agent_id)
    executor = NetworkExecutor(invoker=invoker, store=store)
    processor = object.__new__(NetworkExecutionProcessor)
    processor._store = store

    task = asyncio.create_task(
        processor._execute_with_cancellation(
            execution.id,
            executor.execute(execution, version),
        )
    )
    await asyncio.wait_for(invoker.child_started.wait(), timeout=1)
    await store.request_cancel(execution.id)

    with pytest.raises(NetworkExecutionCancelled):
        await asyncio.wait_for(task, timeout=1)

    assert invoker.child_interrupted.is_set()
    invocations = await store.invocations(execution.id)
    assert len(invocations) == 2
    assert {item["status"] for item in invocations} == {"cancelled"}
    assert all(item.get("failure") is None for item in invocations)
    assert all(item.get("error") is None for item in invocations)
