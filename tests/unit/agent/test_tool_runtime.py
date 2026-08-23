from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.ports import ExecutionResult, McpSessionStorePort, ToolExecutionPort
from modules.agent.application.tool_runtime import (
    ERROR_HTTP_ERROR,
    ERROR_MCP_CONFIG_ERROR,
    ERROR_MCP_TOOL_DENIED_BY_POLICY,
    MCP_AGENT_SESSION_INPUT_KEY,
    MCP_REMOTE_TOOL_INPUT_KEY,
    HttpToolRuntime,
    McpToolRuntime,
)
from modules.agent.domain.enums import ToolType


@dataclass
class FakeTool:
    config: dict
    type: ToolType = ToolType.MCP
    id: object = field(default_factory=uuid4)
    project_id: object = field(default_factory=uuid4)
    timeout_ms: int = 30000
    name: str = "fake-tool"
    description: str | None = None
    input_schema: dict | None = None


class FakeExecutor(ToolExecutionPort):
    def __init__(self, results: list[ExecutionResult] | None = None) -> None:
        self.results = list(results or [])
        self.calls: list[dict] = []

    async def execute(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "body": body, "timeout_ms": timeout_ms})
        if self.results:
            return self.results.pop(0)
        return ExecutionResult(success=True, output={"body": {"result": {"ok": True}}}, duration_ms=1)


class MemoryMcpSessionStore(McpSessionStorePort):
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.deleted: list[str] = []

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, session_id: str, ttl_seconds: int) -> None:
        self.values[key] = session_id

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.values.pop(key, None)


def mcp_tool(permission_mode: str = "allow") -> FakeTool:
    return FakeTool(
        config={
            "protocol": "mcp",
            "mode": "server",
            "server": {"transport": "streamable_http", "url": "https://mcp.example.com/mcp"},
            "discovered_tools": [{"name": "search", "permission": {"mode": permission_mode}}],
        }
    )


@pytest.mark.asyncio
async def test_mcp_runtime_initializes_and_stores_session_on_cache_miss() -> None:
    tool = mcp_tool()
    store = MemoryMcpSessionStore()
    executor = FakeExecutor([
        ExecutionResult(success=True, output={"headers": {"mcp-session-id": "sid-1"}, "body": {"result": {}}}),
        ExecutionResult(success=True, output={"body": {"result": {}}}),
        ExecutionResult(success=True, output={"body": {"result": {"content": [{"type": "text", "text": "ok"}]}}}),
    ])
    runtime = McpToolRuntime(executor, session_store=store)

    result = await runtime.execute(tool, {MCP_AGENT_SESSION_INPUT_KEY: "agent-session-1", MCP_REMOTE_TOOL_INPUT_KEY: "search", "query": "redis"})

    assert result.success is True
    assert len(executor.calls) == 3
    assert store.values == {f"agent-session-1:{tool.id}": "sid-1"}
    tool_call = json.loads(executor.calls[-1]["body"])
    assert tool_call["method"] == "tools/call"
    assert tool_call["params"]["name"] == "search"
    assert tool_call["params"]["arguments"] == {"query": "redis"}


@pytest.mark.asyncio
async def test_mcp_runtime_reuses_cached_session() -> None:
    tool = mcp_tool()
    store = MemoryMcpSessionStore()
    store.values[f"agent-session-1:{tool.id}"] = "sid-cached"
    executor = FakeExecutor([ExecutionResult(success=True, output={"body": {"result": {"content": []}}})])
    runtime = McpToolRuntime(executor, session_store=store)

    result = await runtime.execute(tool, {MCP_AGENT_SESSION_INPUT_KEY: "agent-session-1", MCP_REMOTE_TOOL_INPUT_KEY: "search"})

    assert result.success is True
    assert len(executor.calls) == 1
    assert executor.calls[0]["headers"].get("Mcp-Session-Id") == "sid-cached"


@pytest.mark.asyncio
async def test_mcp_runtime_reinitializes_after_invalid_cached_session() -> None:
    tool = mcp_tool()
    key = f"agent-session-1:{tool.id}"
    store = MemoryMcpSessionStore()
    store.values[key] = "sid-old"
    executor = FakeExecutor([
        ExecutionResult(success=False, error="invalid session", output={"body": {"error": {"message": "invalid session"}}}),
        ExecutionResult(success=True, output={"headers": {"mcp-session-id": "sid-new"}, "body": {"result": {}}}),
        ExecutionResult(success=True, output={"body": {"result": {}}}),
        ExecutionResult(success=True, output={"body": {"result": {"content": []}}}),
    ])
    runtime = McpToolRuntime(executor, session_store=store)

    result = await runtime.execute(tool, {MCP_AGENT_SESSION_INPUT_KEY: "agent-session-1", MCP_REMOTE_TOOL_INPUT_KEY: "search"})

    assert result.success is True
    assert store.deleted == [key]
    assert store.values[key] == "sid-new"
    assert len(executor.calls) == 4


@pytest.mark.asyncio
async def test_mcp_runtime_blocks_denied_discovered_tool_before_remote_call() -> None:
    executor = FakeExecutor()
    runtime = McpToolRuntime(executor)

    result = await runtime.execute(mcp_tool("deny"), {MCP_AGENT_SESSION_INPUT_KEY: "agent-session-1", MCP_REMOTE_TOOL_INPUT_KEY: "search"})

    assert result.success is False
    assert result.output and result.output["error_code"] == ERROR_MCP_TOOL_DENIED_BY_POLICY
    assert executor.calls == []


@pytest.mark.asyncio
async def test_mcp_runtime_returns_config_error_without_tool_name() -> None:
    runtime = McpToolRuntime(FakeExecutor())

    result = await runtime.execute(mcp_tool(), {MCP_AGENT_SESSION_INPUT_KEY: "agent-session-1"})

    assert result.success is False
    assert result.output and result.output["error_code"] == ERROR_MCP_CONFIG_ERROR


@pytest.mark.asyncio
async def test_http_runtime_normalizes_http_failure() -> None:
    executor = FakeExecutor([ExecutionResult(success=False, status_code=500, error="HTTP 500", output={})])
    runtime = HttpToolRuntime(executor)
    tool = FakeTool(type=ToolType.HTTP, config={"protocol": "http", "method": "GET", "url": "https://api.example.com/items"})

    result = await runtime.execute(tool, {})

    assert result.success is False
    assert result.output and result.output["error_code"] == ERROR_HTTP_ERROR
    assert result.output["protocol"] == "http"
