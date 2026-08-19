from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from modules.agent.application.mcp_tool_refresh import refresh_stale_mcp_server_tools
from modules.agent.application.interfaces.ports import ExecutionResult, ToolExecutionPort, ToolSecretResolverPort
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import RiskLevel, ToolStatus, ToolType
from modules.agent.application.interfaces.repositories import ToolRepository
from shared.infra.objects import CursorPage
from shared.infra.time import utc_now


class FakeExecutor(ToolExecutionPort):
    def __init__(self) -> None:
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
        if len(self.calls) == 1:
            return ExecutionResult(success=True, output={"headers": {"mcp-session-id": "sid"}, "body": {"result": {}}})
        return ExecutionResult(
            success=True,
            output={
                "body": {
                    "result": {
                        "tools": [
                            {
                                "name": "search",
                                "description": "Search docs",
                                "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}},
                            }
                        ]
                    }
                }
            },
        )


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
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "body": body, "timeout_ms": timeout_ms})
        if not self.results:
            raise AssertionError("Unexpected executor call")
        return self.results.pop(0)


class FakeSecretResolver(ToolSecretResolverPort):
    def __init__(self) -> None:
        self.calls: list[tuple[list[dict], UUID]] = []

    async def resolve_headers(self, headers: list[dict], project_id: UUID) -> dict[str, str]:
        self.calls.append((headers, project_id))
        return {"Authorization": "Bearer resolved-token"}


@dataclass
class FakeToolRepository(ToolRepository):
    updated: list[Tool] = field(default_factory=list)

    async def create(self, tool: Tool) -> Tool:
        return tool

    async def get_by_id(self, tool_id: UUID) -> Tool:
        raise AssertionError("not used")

    async def list_by_project(self, project_id: UUID, status: str | None = None) -> list[Tool]:
        return []

    async def list_by_agent(self, agent_id: UUID, status: str | None = None) -> list[Tool]:
        return []

    async def paginate_by_project(self, project_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None) -> CursorPage[Tool]:
        return CursorPage(items=[], cursor=None, next_cursor=None, has_next=False, total=0)

    async def paginate_by_agent(self, agent_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None) -> CursorPage[Tool]:
        return CursorPage(items=[], cursor=None, next_cursor=None, has_next=False, total=0)

    async def update(self, tool: Tool) -> Tool:
        self.updated.append(tool)
        return tool

    async def delete(self, tool_id: UUID) -> None:
        return None


def mcp_provider(config: dict | None = None) -> Tool:
    return Tool(
        id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        name="MCP Provider",
        type=ToolType.MCP,
        config=config or {
            "protocol": "mcp",
            "mode": "server",
            "exposure": "all_discovered",
            "server": {"transport": "streamable_http", "url": "https://mcp.example.com"},
            "discovery_cache_ttl_seconds": 3600,
            "discovered_tools": [],
        },
        risk_level=RiskLevel.LOW,
        status=ToolStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_refresh_stale_mcp_server_tools_discovers_and_persists_tools() -> None:
    tool = mcp_provider()
    repo = FakeToolRepository()
    executor = FakeExecutor()

    refreshed = await refresh_stale_mcp_server_tools(tools=[tool], tool_repo=repo, executor=executor)

    assert refreshed[0].config is not None
    assert refreshed[0].config["discovered_tools"][0]["name"] == "search"
    assert refreshed[0].config["discovered_at"]
    assert repo.updated == [refreshed[0]]
    assert len(executor.calls) == 3


@pytest.mark.asyncio
async def test_refresh_stale_mcp_server_tools_resolves_secret_headers() -> None:
    tool = mcp_provider(
        {
            "protocol": "mcp",
            "mode": "server",
            "exposure": "all_discovered",
            "server": {
                "transport": "streamable_http",
                "url": "https://mcp.example.com",
                "headers": [{"key": "Authorization", "value": "secret://mcp-token", "sensitive": True}],
            },
            "discovery_cache_ttl_seconds": 3600,
            "discovered_tools": [],
        }
    )
    repo = FakeToolRepository()
    executor = FakeExecutor()
    resolver = FakeSecretResolver()

    await refresh_stale_mcp_server_tools(
        tools=[tool],
        tool_repo=repo,
        executor=executor,
        secret_resolver=resolver,
    )

    assert resolver.calls == [(
        [{"key": "Authorization", "value": "secret://mcp-token", "sensitive": True}],
        tool.project_id,
    )]
    assert executor.calls[0]["headers"]["Authorization"] == "Bearer resolved-token"


@pytest.mark.asyncio
async def test_refresh_stale_mcp_server_tools_skips_fresh_cache() -> None:
    tool = mcp_provider(
        {
            "protocol": "mcp",
            "mode": "server",
            "exposure": "all_discovered",
            "server": {"transport": "streamable_http", "url": "https://mcp.example.com"},
            "discovery_cache_ttl_seconds": 3600,
            "discovered_at": (utc_now() + timedelta(seconds=30)).isoformat(),
            "discovered_tools": [{"name": "existing"}],
        }
    )
    repo = FakeToolRepository()
    executor = FakeExecutor()

    refreshed = await refresh_stale_mcp_server_tools(tools=[tool], tool_repo=repo, executor=executor)

    assert refreshed == [tool]
    assert repo.updated == []
    assert executor.calls == []


@pytest.mark.asyncio
async def test_refresh_classifies_incomplete_run_tools_oauth_as_managed_provider() -> None:
    server_url = "https://skillflow--rafsilva85.run.tools"
    resource_metadata_url = f"{server_url}/.well-known/oauth-protected-resource"
    tool = mcp_provider(
        {
            "protocol": "mcp",
            "mode": "server",
            "exposure": "all_discovered",
            "server": {"transport": "streamable_http", "url": server_url},
            "discovery_cache_ttl_seconds": 0,
            "discovered_tools": [],
        }
    )
    repo = FakeToolRepository()
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
            output={"body": {"authorization_servers": ["https://auth.smithery.example"]}},
        ),
        ExecutionResult(success=False, status_code=404, error="Not found"),
        ExecutionResult(success=False, status_code=404, error="Not found"),
    ])

    refreshed = await refresh_stale_mcp_server_tools(tools=[tool], tool_repo=repo, executor=executor)

    assert refreshed[0].config["mcp_status"] == "provider_managed"
    assert refreshed[0].config["mcp_oauth_discovery"]["status"] == "provider_managed"
    assert refreshed[0].config["mcp_oauth_discovery"]["provider"] == "smithery"
    assert refreshed[0].config["mcp_readiness"]["state"] == "provider_managed"
    assert refreshed[0].config["mcp_readiness"]["action"] == "provider_credentials"
    assert len(executor.calls) == 4
