from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest

from modules.network.application.runtime import (
    AgentInvocationResult,
    NetworkExecutionCancelled,
    NetworkExecutionSnapshot,
    NetworkExecutor,
    NetworkVersionSnapshot,
)
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from modules.network.infra.workers.execution_worker import NetworkExecutionProcessor
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _DeepDelegatingInvoker:
    def __init__(self, root_agent_id: UUID, middle_agent_id: UUID, leaf_agent_id: UUID) -> None:
        self.root_agent_id = root_agent_id
        self.middle_agent_id = middle_agent_id
        self.leaf_agent_id = leaf_agent_id
        self.leaf_started = asyncio.Event()
        self.leaf_interrupted = asyncio.Event()

    async def invoke(self, *, agent_id, internal_tools, **_kwargs):
        if agent_id == self.root_agent_id:
            assert len(internal_tools) == 1
            result = await internal_tools[0].handler({"task": "coordinate specialist"})
            return AgentInvocationResult(answer=str(result))

        if agent_id == self.middle_agent_id:
            assert len(internal_tools) == 1
            result = await internal_tools[0].handler({"task": "perform deep specialist work"})
            return AgentInvocationResult(answer=str(result))

        assert agent_id == self.leaf_agent_id
        assert internal_tools == []
        self.leaf_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.leaf_interrupted.set()
            raise


@pytest.mark.asyncio
async def test_cancel_during_deep_delegation_cancels_entire_in_flight_chain() -> None:
    root_node_id = uuid4()
    middle_node_id = uuid4()
    leaf_node_id = uuid4()
    root_agent_id = uuid4()
    middle_agent_id = uuid4()
    leaf_agent_id = uuid4()
    execution = NetworkExecutionSnapshot(
        id=uuid4(),
        network_id=uuid4(),
        network_version_id=uuid4(),
        network_session_id=uuid4(),
        project_id=uuid4(),
        input_message="ask the specialist chain",
        draft_revision=None,
        definition_snapshot=None,
        resolved_bindings_snapshot=None,
        status="queued",
    )
    release_ids = {
        root_node_id: uuid4(),
        middle_node_id: uuid4(),
        leaf_node_id: uuid4(),
    }
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
                    "capability_description": "Coordinates a specialist chain.",
                    "position": {"x": 0, "y": 0},
                    "binding": {
                        "source": "release",
                        "release_id": str(release_ids[root_node_id]),
                    },
                },
                {
                    "id": str(middle_node_id),
                    "agent_id": str(middle_agent_id),
                    "label": "Coordinator",
                    "capability_description": "Coordinates deep specialist work.",
                    "position": {"x": 300, "y": 0},
                    "binding": {
                        "source": "release",
                        "release_id": str(release_ids[middle_node_id]),
                    },
                },
                {
                    "id": str(leaf_node_id),
                    "agent_id": str(leaf_agent_id),
                    "label": "Leaf specialist",
                    "capability_description": "Performs the final specialist task.",
                    "position": {"x": 600, "y": 0},
                    "binding": {
                        "source": "release",
                        "release_id": str(release_ids[leaf_node_id]),
                    },
                },
            ],
            "edges": [
                {
                    "id": str(uuid4()),
                    "source_node_id": str(root_node_id),
                    "target_node_id": str(middle_node_id),
                },
                {
                    "id": str(uuid4()),
                    "source_node_id": str(middle_node_id),
                    "target_node_id": str(leaf_node_id),
                },
            ],
            "settings": {
                "session_mode": "stateless",
                "max_depth": 4,
                "max_invocations": 16,
                "timeout_seconds": 30,
            },
        },
        resolved_bindings={
            str(node_id): {
                "release_id": str(release_id),
                "session_mode": "stateless",
            }
            for node_id, release_id in release_ids.items()
        },
    )

    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    await store.initialize(execution, ttl_seconds=3600)
    invoker = _DeepDelegatingInvoker(
        root_agent_id,
        middle_agent_id,
        leaf_agent_id,
    )
    executor = NetworkExecutor(invoker=invoker, store=store)
    processor = object.__new__(NetworkExecutionProcessor)
    processor._store = store

    task = asyncio.create_task(
        processor._execute_with_cancellation(
            execution.id,
            executor.execute(execution, version),
        )
    )
    await asyncio.wait_for(invoker.leaf_started.wait(), timeout=1)
    await store.request_cancel(execution.id)

    with pytest.raises(NetworkExecutionCancelled):
        await asyncio.wait_for(task, timeout=2)

    assert invoker.leaf_interrupted.is_set()
    invocations = await store.invocations(execution.id)
    assert len(invocations) == 3
    assert [int(item["depth"]) for item in invocations] == [0, 1, 2]
    assert {item["status"] for item in invocations} == {"cancelled"}
    assert all(item.get("failure") is None for item in invocations)
    assert all(item.get("error") is None for item in invocations)
