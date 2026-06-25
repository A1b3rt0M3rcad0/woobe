import uuid

import pytest

from modules.agent.application.mcp_tool_bootstrap import McpToolBootstrapper
from modules.agent.application.ports import ExecutionResult, ToolExecutionPort
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import ToolType


class SequenceExecutor(ToolExecutionPort):
    def __init__(self, results: list[ExecutionResult]) -> None:
        self.results = results
        self.calls: list[dict] = []

    async def execute(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body, "timeout_ms": timeout_ms})
        if not self.results:
            raise AssertionError("Unexpected executor call")
        return self.results.pop(0)


def mcp_tool() -> Tool:
    return Tool(
        project_id=uuid.uuid4(),
        name="Test MCP",
        type=ToolType.MCP,
        config={
            "protocol": "mcp",
            "mode": "server",
            "exposure": "all_discovered",
            "server": {"transport": "streamable_http", "url": "https://mcp.example.com", "headers": []},
            "discovered_tools": [],
        },
    )


@pytest.mark.asyncio
async def test_bootstrap_loads_public_mcp_tools_on_create() -> None:
    executor = SequenceExecutor([
        ExecutionResult(success=True, status_code=200, output={"body": {"result": {}}}),
        ExecutionResult(success=True, status_code=202, output={"body": {"ok": True}}),
        ExecutionResult(success=True, status_code=200, output={"body": {"result": {"tools": [{"name": "search", "description": "Search", "inputSchema": {"type": "object"}}]}}}),
    ])
    tool = mcp_tool()

    result = await McpToolBootstrapper(executor).bootstrap(tool)

    assert result is not None
    assert result.status == "ready"
    assert result.discovered_count == 1
    assert len(executor.calls) == 3
    assert tool.config["mcp_status"] == "ready"
    assert tool.config["discovered_tools"][0]["name"] == "search"
    assert tool.config["mcp_readiness"]["state"] == "needs_permission"
    assert tool.config["mcp_readiness"]["action"] == "configure_permissions"


@pytest.mark.asyncio
async def test_bootstrap_marks_oauth_required_without_failing_create() -> None:
    executor = SequenceExecutor([
        ExecutionResult(
            success=False,
            status_code=401,
            error="Unauthorized",
            headers={"www-authenticate": "Bearer resource_metadata=\"https://mcp.example.com/.well-known/oauth-protected-resource\""},
        ),
    ])
    tool = mcp_tool()

    result = await McpToolBootstrapper(executor).bootstrap(tool)

    assert result is not None
    assert result.status == "needs_connection"
    assert tool.config["mcp_status"] == "needs_connection"
    assert tool.config["mcp_readiness"]["state"] == "needs_connection"
    assert tool.config["mcp_readiness"]["action"] == "connect"
    assert tool.config["discovered_tools"] == []
