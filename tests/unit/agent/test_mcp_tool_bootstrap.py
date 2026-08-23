import uuid

import pytest

from modules.agent.application.mcp_tool_bootstrap import McpToolBootstrapper
from modules.agent.application.interfaces.ports import ExecutionResult, ToolExecutionPort
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


def mcp_tool(server_url: str = "https://mcp.example.com") -> Tool:
    return Tool(
        project_id=uuid.uuid4(),
        name="Test MCP",
        type=ToolType.MCP,
        config={
            "protocol": "mcp",
            "mode": "server",
            "exposure": "all_discovered",
            "server": {"transport": "streamable_http", "url": server_url, "headers": []},
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
async def test_bootstrap_shows_connect_only_after_complete_oauth_metadata_validation() -> None:
    resource_metadata_url = "https://mcp.example.com/.well-known/oauth-protected-resource"
    executor = SequenceExecutor([
        ExecutionResult(
            success=False,
            status_code=401,
            error="Unauthorized",
            headers={"www-authenticate": f"Bearer resource_metadata=\"{resource_metadata_url}\""},
        ),
        ExecutionResult(
            success=True,
            status_code=200,
            output={
                "body": {
                    "resource": "https://mcp.example.com",
                    "authorization_servers": ["https://auth.example.com"],
                }
            },
        ),
        ExecutionResult(
            success=True,
            status_code=200,
            output={
                "body": {
                    "issuer": "https://auth.example.com",
                    "authorization_endpoint": "https://auth.example.com/authorize",
                    "token_endpoint": "https://auth.example.com/token",
                    "registration_endpoint": "https://auth.example.com/register",
                }
            },
        ),
    ])
    tool = mcp_tool()

    result = await McpToolBootstrapper(executor).bootstrap(tool)

    assert result is not None
    assert result.status == "oauth_required"
    assert tool.config["mcp_status"] == "oauth_required"
    assert tool.config["mcp_oauth_discovery"]["status"] == "valid"
    assert tool.config["mcp_oauth_discovery"]["authorization_endpoint"] == "https://auth.example.com/authorize"
    assert tool.config["mcp_oauth_discovery"]["token_endpoint"] == "https://auth.example.com/token"
    assert tool.config["mcp_readiness"]["state"] == "needs_connection"
    assert tool.config["mcp_readiness"]["action"] == "connect"
    assert len(executor.calls) == 3


@pytest.mark.asyncio
async def test_bootstrap_classifies_run_tools_with_incomplete_oauth_as_managed_provider() -> None:
    server_url = "https://skillflow--rafsilva85.run.tools"
    resource_metadata_url = f"{server_url}/.well-known/oauth-protected-resource"
    executor = SequenceExecutor([
        ExecutionResult(
            success=False,
            status_code=401,
            error="Unauthorized",
            headers={"www-authenticate": f"Bearer resource_metadata=\"{resource_metadata_url}\""},
        ),
        ExecutionResult(
            success=True,
            status_code=200,
            output={
                "body": {
                    "resource": server_url,
                    "authorization_servers": ["https://auth.smithery.example"],
                }
            },
        ),
        ExecutionResult(success=False, status_code=404, error="Not found"),
        ExecutionResult(success=False, status_code=404, error="Not found"),
    ])
    tool = mcp_tool(server_url)

    result = await McpToolBootstrapper(executor).bootstrap(tool)

    assert result is not None
    assert result.status == "provider_managed"
    assert tool.config["mcp_status"] == "provider_managed"
    assert tool.config["mcp_oauth_discovery"]["status"] == "provider_managed"
    assert tool.config["mcp_oauth_discovery"]["provider"] == "smithery"
    assert tool.config["mcp_readiness"]["state"] == "provider_managed"
    assert tool.config["mcp_readiness"]["action"] == "provider_credentials"
    assert "Could not discover MCP OAuth authorization and token endpoints" not in (result.error or "")
    assert len(executor.calls) == 4
