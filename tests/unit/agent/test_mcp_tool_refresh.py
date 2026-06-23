from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from modules.agent.application.mcp_tool_refresh import refresh_stale_mcp_server_tools
from modules.agent.application.ports import ExecutionResult, ToolExecutionPort
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import RiskLevel, ToolStatus, ToolType
from modules.agent.domain.repositories import ToolRepository
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
