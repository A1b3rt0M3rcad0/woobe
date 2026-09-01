from __future__ import annotations

import asyncio
from contextlib import suppress
from uuid import uuid4

import pytest

from modules.agent.infra.execution.runtime_streaming import (
    RuntimeStreamChannel,
    current_runtime_stream,
    invoke_model_with_optional_streaming,
)
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


class _Chunk:
    def __init__(self, content: str = "") -> None:
        self.content = content
        self.tool_calls = []
        self.tool_call_chunks = []

    def __add__(self, other: "_Chunk") -> "_Chunk":
        return _Chunk(self.content + other.content)


class _BlockingModel:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.interrupted = asyncio.Event()

    async def astream(self, _messages):
        yield _Chunk("partial root output")
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.interrupted.set()
            raise


class _RuntimePhaseInvoker:
    def __init__(self, model: _BlockingModel, phase: str) -> None:
        self.model = model
        self.phase = phase

    async def invoke(self, *, stream_handler=None, **_kwargs):
        assert stream_handler is not None
        channel = RuntimeStreamChannel()
        token = current_runtime_stream.set(channel)
        task = asyncio.create_task(
            invoke_model_with_optional_streaming(
                model=self.model,
                messages=[],
                phase=self.phase,
                provider="test-provider",
                model_name="test-model",
            )
        )
        try:
            while not task.done():
                try:
                    event = await asyncio.wait_for(channel.queue.get(), timeout=0.05)
                except asyncio.TimeoutError:
                    continue
                await stream_handler(event.event_type, dict(event.payload))
            result = await task
            while not channel.queue.empty():
                event = channel.queue.get_nowait()
                await stream_handler(event.event_type, dict(event.payload))
            return AgentInvocationResult(
                answer=result.content,
                provider="test-provider",
                model="test-model",
                streamed_output=True,
            )
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            current_runtime_stream.reset(token)


def _runtime():
    node_id = uuid4()
    agent_id = uuid4()
    execution = NetworkExecutionSnapshot(
        id=uuid4(),
        network_id=uuid4(),
        network_version_id=uuid4(),
        network_session_id=uuid4(),
        project_id=uuid4(),
        input_message="produce a long root response",
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
                    "capability_description": "Produces the final response.",
                    "position": {"x": 0, "y": 0},
                    "binding": {"source": "release", "release_id": str(uuid4())},
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
@pytest.mark.parametrize("phase", ["tool_followup_1", "final_response_generation"])
async def test_network_cancel_interrupts_active_root_response_phase(phase: str) -> None:
    execution, version = _runtime()
    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    await store.initialize(execution, ttl_seconds=3600)
    model = _BlockingModel()
    executor = NetworkExecutor(invoker=_RuntimePhaseInvoker(model, phase), store=store)
    processor = object.__new__(NetworkExecutionProcessor)
    processor._store = store

    task = asyncio.create_task(
        processor._execute_with_cancellation(
            execution.id,
            executor.execute(execution, version),
        )
    )
    await asyncio.wait_for(model.started.wait(), timeout=1)
    await store.request_cancel(execution.id)

    with pytest.raises(NetworkExecutionCancelled):
        await asyncio.wait_for(task, timeout=1)

    assert model.interrupted.is_set()
    invocations = await store.invocations(execution.id)
    assert len(invocations) == 1
    assert invocations[0]["status"] == "cancelled"
    assert invocations[0].get("failure") is None
