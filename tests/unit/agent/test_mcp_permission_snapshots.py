from uuid import uuid4

import pytest

from modules.agent.application.mcp_permissions import merge_discovered_tools_with_existing_permissions
from modules.agent.application.tool_release_snapshots import (
    build_release_tool_runtime,
    tool_from_release_snapshot,
    tool_with_permission_overrides,
)
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import ToolStatus, ToolType


class FakeToolRepository:
    def __init__(self, tool: Tool) -> None:
        self.tool = tool

    async def get_by_id(self, tool_id):
        return self.tool if tool_id == self.tool.id else None


def make_mcp_tool() -> Tool:
    return Tool(
        id=uuid4(),
        project_id=uuid4(),
        name="provider",
        type=ToolType.MCP,
        status=ToolStatus.ACTIVE,
        config={
            "protocol": "mcp",
            "mode": "server",
            "exposure": "all_discovered",
            "server": {"transport": "streamable_http", "url": "https://example.com/mcp"},
            "discovered_tools": [
                {"name": "search", "permission": {"mode": "allow"}},
                {"name": "admin", "permission": {"mode": "deny"}},
            ],
        },
    )


def test_refresh_merge_preserves_existing_permission_over_discovery_default():
    merged = merge_discovered_tools_with_existing_permissions(
        [{"name": "search", "permission": {"mode": "review", "risk_level": "unknown"}}],
        [{"name": "search", "permission": {"mode": "allow"}}],
    )

    assert merged[0]["permission"]["mode"] == "allow"


def test_draft_permission_overrides_are_agent_scoped_and_default_missing_tools_to_review():
    tool = make_mcp_tool()

    overridden = tool_with_permission_overrides(
        tool,
        {"search": {"mode": "deny"}},
    )

    original_tools = tool.config["discovered_tools"]
    overridden_tools = overridden.config["discovered_tools"]

    assert original_tools[0]["permission"]["mode"] == "allow"
    assert original_tools[1]["permission"]["mode"] == "deny"
    assert overridden_tools[0]["permission"]["mode"] == "deny"
    assert overridden_tools[1]["permission"]["mode"] == "review"
    assert overridden is not tool


@pytest.mark.asyncio
async def test_release_tool_snapshot_materializes_draft_permissions_without_mutating_tool():
    tool = make_mcp_tool()
    repo = FakeToolRepository(tool)

    runtime = await build_release_tool_runtime(
        repo,
        project_id=tool.project_id,
        raw_tool_ids=[str(tool.id)],
        raw_permissions={
            str(tool.id): {
                "search": {"mode": "allow"},
            }
        },
    )

    snapshot = runtime["snapshots"][0]
    restored = tool_from_release_snapshot(snapshot)
    restored_tools = restored.config["discovered_tools"]

    assert runtime["tool_ids"] == [str(tool.id)]
    assert restored_tools[0]["permission"]["mode"] == "allow"
    assert restored_tools[1]["permission"]["mode"] == "review"
    assert tool.config["discovered_tools"][1]["permission"]["mode"] == "deny"
