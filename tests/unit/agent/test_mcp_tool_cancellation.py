from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.ports import ExecutionResult
from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.adapters.tool_runtime import McpToolRuntime
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.runtime_streaming import current_runtime_stream
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _Outbox:
    async def write(self, _event) -> None:
        return None


class _Runs:
    def __init__(self, run: AgentRun) -> None:
        self.run = run

    async def get_by_id(self, run_id):
        return self.run if self.run.id == run_id else None

    async def get_by_id_for_update(self, run_id):
        return await self.get_by_id(run_id)

    async def save(self, run):
        self.run = run
        return run


class _Transactions:
    def __init__(self, run: AgentRun) -> None:
        self.repositories = SimpleNamespace(runs=_Runs(run))
        self.outbox = _Outbox()

    async def run(self, operation):
        return await operation(self.repositories, self.outbox)

    async def read(self, operation):
        return await operation(self.repositories, self.outbox)


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


class _McpUseCase:
    def __init__(self, run: AgentRun, store: InMemoryExecutionStateStore, executor: _BlockingMcpExecutor) -> None:
        self.run = run
        self.store = store
        self.runtime = McpToolRuntime(executor)

    async def execute(self, _input_dto):
        channel = current_runtime_stream.get()
        assert channel is not None
        channel.bind_execution(
            trace_id=self.run.trace_id,
            session_id=self.run.session_id,
            project_id=self.run.project_id,
            agent_id=self.run.agent_id,
        )
        setattr(channel, "run_id", self.run.id)
        await self.store.create(
            self.run.id,
            {
                "status": "running",
                "session_id": str(self.run.session_id),
                "project_id": str(self.run.project_id),
                "agent_id": str(self.run.agent_id),
            },
            ttl_seconds=3600,
        )
        await channel.emit(
            "meta",
            run_id=str(self.run.id),
            trace_id=str(self.run.trace_id),
            project_id=str(self.run.project_id),
            agent_id=str(self.run.agent_id),
        )
        await channel.emit("tool_call_started", tool_name="lookup_customer", tool_call_id="mcp-call-1")
        await self.runtime.test(
            {
                "server": {"transport": "streamable_http", "url": "https://mcp.example.test/mcp"},
                "tool_name": "lookup_customer",
            },
            {"customer_id": "123"},
            timeout_ms=30_000,
        )
        raise AssertionError("MCP execution should have been cancelled")


def _run() -> AgentRun:
    return AgentRun(
        session_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="playground",
        input_message="call MCP",
        execution_snapshot={},
    )


async def _next_frame(stream, event_type: str) -> str:
    while True:
        frame = await asyncio.wait_for(anext(stream), timeout=2)
        if f"event: {event_type}" in frame:
            return frame


@pytest.mark.asyncio
async def test_agent_stop_interrupts_streamable_http_mcp_tool_without_failure_terminal() -> None:
    run = _run()
    store = InMemoryExecutionStateStore()
    executor = _BlockingMcpExecutor()
    transactions = _Transactions(run)
    service = AskAgentStreamService(_McpUseCase(run, store, executor), transactions, state_store=store)
    input_dto = AskInput(
        project_id=run.project_id,
        agent_id=run.agent_id,
        message=run.input_message,
        execution_context="playground",
    )

    stream = service.stream(input_dto)
    try:
        await _next_frame(stream, "meta")
        await asyncio.wait_for(executor.tool_started.wait(), timeout=1)
        await store.request_cancel(run.id)

        terminal = await _next_frame(stream, "cancelled")

        assert '"persisted": true' in terminal
        assert transactions.repositories.runs.run.status == AgentRunStatus.CANCELLED
        assert transactions.repositories.runs.run.failure_code is None
        assert transactions.repositories.runs.run.failure_detail is None
        await asyncio.wait_for(executor.tool_interrupted.wait(), timeout=1)
    finally:
        await stream.aclose()
