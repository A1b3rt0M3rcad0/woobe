from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.ports import ExecutionResult
from modules.agent.infra.adapters.tool_runtime import McpToolRuntime
from modules.network.application.runtime import NetworkExecutionCancelled, NetworkExecutionSnapshot
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from modules.network.infra.workers.execution_worker import NetworkExecutionProcessor
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _BlockingMcpExecutor:
    def __init__(self) -> None:
        self.calls = 0
        self.tool_started = asyncio.Event()
        self.tool_interrupted = asyncio.Event()

    async def execute(self, *, method, url, headers=None, body=None, timeout_ms=30000):
        del method, url, headers, body, timeout_ms
        self.calls += 1
        if self.calls == 1:
            return ExecutionResult(
                success=True,
                status_code=200,
                output={"headers": {"mcp-session-id": "remote-session-1"}},
            )
        if self.calls == 2:
            return ExecutionResult(success=True, status_code=202, output={})

        self.tool_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.tool_interrupted.set()
            raise


@pytest.mark.asyncio
async def test_network_cancel_interrupts_streamable_http_mcp_tool_in_flight() -> None:
    execution = NetworkExecutionSnapshot(
        id=uuid4(),
        network_id=uuid4(),
        network_version_id=uuid4(),
        network_session_id=uuid4(),
        project_id=uuid4(),
        input_message="call MCP capability",
        draft_revision=None,
        definition_snapshot=None,
        resolved_bindings_snapshot=None,
        status="queued",
    )
    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    await store.initialize(execution, ttl_seconds=3600)

    executor = _BlockingMcpExecutor()
    runtime = McpToolRuntime(executor)
    processor = object.__new__(NetworkExecutionProcessor)
    processor._store = store

    task = asyncio.create_task(
        processor._execute_with_cancellation(
            execution.id,
            runtime.test(
                {
                    "server": {
                        "transport": "streamable_http",
                        "url": "https://mcp.example.test/mcp",
                    },
                    "tool_name": "lookup_customer",
                },
                {"customer_id": "123"},
                timeout_ms=30_000,
            ),
        )
    )

    await asyncio.wait_for(executor.tool_started.wait(), timeout=1)
    await store.request_cancel(execution.id)

    with pytest.raises(NetworkExecutionCancelled):
        await asyncio.wait_for(task, timeout=1)

    assert executor.tool_interrupted.is_set()
