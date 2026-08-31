from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from modules.network.application.runtime import (
    NetworkExecutionCancelled,
    NetworkExecutionSnapshot,
    NetworkExecutor,
    NetworkVersionSnapshot,
)
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from modules.network.infra.workers.execution_worker import NetworkExecutionProcessor
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _TelemetryBlockingInvoker:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.interrupted = asyncio.Event()

    async def invoke(self, **kwargs):
        stream_handler = kwargs["stream_handler"]
        assert stream_handler is not None
        await stream_handler(
            "agent_activity",
            {
                "status": "generating_answer",
                "phase": "capability_response_generation",
                "message": "Generating response...",
                "provider": "custom",
                "model": "deepseek-v4-flash",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.interrupted.set()
            raise


def _execution_and_version() -> tuple[NetworkExecutionSnapshot, NetworkVersionSnapshot]:
    node_id = uuid4()
    agent_id = uuid4()
    execution = NetworkExecutionSnapshot(
        id=uuid4(),
        network_id=uuid4(),
        network_version_id=uuid4(),
        network_session_id=uuid4(),
        project_id=uuid4(),
        input_message="generate a long answer",
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
            "root_node_id": str(node_id),
            "nodes": [
                {
                    "id": str(node_id),
                    "agent_id": str(agent_id),
                    "label": "Root",
                    "capability_description": "Produces the final answer.",
                    "position": {"x": 0, "y": 0},
                    "binding": {
                        "source": "release",
                        "release_id": str(uuid4()),
                    },
                }
            ],
            "edges": [],
            "settings": {
                "session_mode": "stateless",
                "max_depth": 4,
                "max_invocations": 16,
                "timeout_seconds": 30,
            },
        },
        resolved_bindings={
            str(node_id): {
                "release_id": str(uuid4()),
                "session_mode": "stateless",
            }
        },
    )
    return execution, version


@pytest.mark.asyncio
async def test_cancelled_network_root_preserves_active_llm_telemetry_in_hot_state() -> None:
    execution, version = _execution_and_version()
    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    await store.initialize(execution, ttl_seconds=3600)
    invoker = _TelemetryBlockingInvoker()
    executor = NetworkExecutor(invoker=invoker, store=store)
    processor = object.__new__(NetworkExecutionProcessor)
    processor._store = store

    task = asyncio.create_task(
        processor._execute_with_cancellation(
            execution.id,
            executor.execute(execution, version),
        )
    )
    await asyncio.wait_for(invoker.started.wait(), timeout=1)
    await store.request_cancel(execution.id)

    with pytest.raises(NetworkExecutionCancelled):
        await asyncio.wait_for(task, timeout=1)

    assert invoker.interrupted.is_set()
    invocations = await store.invocations(execution.id)
    assert len(invocations) == 1
    invocation = invocations[0]
    assert invocation["status"] == "cancelled"

    diagnostics = invocation.get("diagnostics")
    assert isinstance(diagnostics, dict)
    assert diagnostics["schema_version"] == 5
    assert diagnostics["llm_call_count"] == 1
    assert diagnostics["usage_complete"] is False
    assert diagnostics["cost_status"] == "unknown_tokens"
    assert diagnostics["llm_work_latency_ms"] >= 0

    calls = invocation.get("llm_calls")
    assert isinstance(calls, list) and len(calls) == 1
    assert calls[0]["status"] == "cancelled"
    assert calls[0]["phase"] == "capability_response_generation"
    assert calls[0]["provider"] == "custom"
    assert calls[0]["model"] == "deepseek-v4-flash"
    assert calls[0]["usage_complete"] is False
