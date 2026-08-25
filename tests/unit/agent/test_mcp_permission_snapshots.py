from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.mcp_permissions import merge_discovered_tools_with_existing_permissions
from modules.agent.application.tool_release_snapshots import (
    build_release_tool_runtime,
    tool_from_release_snapshot,
    tool_with_permission_overrides,
)
from modules.agent.application.interfaces.execution_context import current_execution, new_execution_context
from modules.agent.infra.execution.release_runtime_resolver import ReleaseRuntimeResolver
from modules.agent.domain.entities import Agent, AgentRelease, Tool
from modules.agent.domain.enums import ReleaseStatus, ToolStatus, ToolType


class FakeToolRepository:
    def __init__(self, tool: Tool) -> None:
        self.tool = tool

    async def get_by_id(self, tool_id):
        return self.tool if tool_id == self.tool.id else None


class FakeAgentRepository:
    def __init__(self, agent: Agent) -> None:
        self.agent = agent

    async def get_by_id(self, agent_id):
        return self.agent if agent_id == self.agent.id else None


class FakeReleaseRepository:
    def __init__(self, production: AgentRelease | None = None) -> None:
        self.production = production

    async def get_active_production(self, agent_id):
        if self.production is not None and self.production.agent_id == agent_id:
            return self.production
        return None


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


@pytest.mark.asyncio
async def test_draft_runtime_materializes_agent_permission_snapshot_for_execution():
    tool = make_mcp_tool()
    tool.config["discovered_tools"][0]["permission"] = {
        "mode": "review",
        "risk_level": "unknown",
    }
    agent = Agent(
        project_id=tool.project_id,
        model="test-model",
        settings={
            "runtime_config": {
                "tools": {
                    "tool_ids": [str(tool.id)],
                    "permissions": {
                        str(tool.id): {
                            "search": {"mode": "allow"},
                            "admin": {"mode": "deny"},
                        }
                    },
                }
            }
        },
    )

    async def read_runtime_tools(tool_ids):
        assert tool_ids == [tool.id]
        return [tool]

    resolver = object.__new__(ReleaseRuntimeResolver)
    resolver._runtime_tool_reader = read_runtime_tools
    prepared = [None] * 13
    prepared[0] = agent
    prepared[7] = []
    prepared[8] = {}
    prepared[9] = False

    context = new_execution_context()
    token = current_execution.set(context)
    try:
        updated = await resolver._apply_runtime_tool_selection(tuple(prepared))
    finally:
        current_execution.reset(token)

    assert context.tool_metadata is not None
    assert context.tool_metadata["source"] == "draft_live"
    assert context.tool_snapshots is not None
    effective_snapshot = context.tool_snapshots[str(tool.id)]
    effective_tool = tool_from_release_snapshot(effective_snapshot)
    effective_permissions = {
        item["name"]: item["permission"]["mode"]
        for item in effective_tool.config["discovered_tools"]
    }

    assert effective_permissions == {"search": "allow", "admin": "deny"}
    assert tool.config["discovered_tools"][0]["permission"]["mode"] == "review"
    assert updated[9] is True


@pytest.mark.asyncio
async def test_playground_snapshot_override_uses_unsaved_agent_runtime_config():
    project_id = uuid4()
    agent = Agent(
        project_id=project_id,
        model="test-model",
        settings={
            "preserved": "value",
            "runtime_config": {"tools": {"tool_ids": ["saved"]}},
        },
    )
    unsaved_runtime_config = {
        "tools": {
            "tool_ids": ["unsaved"],
            "permissions": {"unsaved": {"remote": {"mode": "allow"}}},
        }
    }
    uow = SimpleNamespace(
        agents=FakeAgentRepository(agent),
        releases=None,
        provider_models=None,
    )
    input_dto = SimpleNamespace(
        agent_id=agent.id,
        project_id=project_id,
        execution_context="playground",
        snapshot_override={"runtime_config": unsaved_runtime_config},
        loaded_release_id=None,
        session_id=None,
        metadata=None,
    )
    resolver = object.__new__(ReleaseRuntimeResolver)

    resolved = await resolver._load_agent(uow, input_dto)

    assert resolved.settings["preserved"] == "value"
    assert resolved.settings["runtime_config"] == unsaved_runtime_config
    assert resolved.settings["runtime_config"] is not unsaved_runtime_config


@pytest.mark.asyncio
async def test_production_runtime_uses_release_tool_snapshot_config_not_live_agent_config():
    project_id = uuid4()
    agent = Agent(
        project_id=project_id,
        model="test-model",
        settings={
            "preserved": "value",
            "runtime_config": {"tools": {"tool_ids": ["live-agent-tool"]}},
        },
    )
    release_runtime_config = {
        "tools": {
            "tool_ids": ["release-tool"],
            "snapshots": [],
        }
    }
    release = AgentRelease(
        project_id=project_id,
        agent_id=agent.id,
        status=ReleaseStatus.production,
        runtime_config=release_runtime_config,
    )
    uow = SimpleNamespace(
        agents=FakeAgentRepository(agent),
        releases=FakeReleaseRepository(production=release),
        provider_models=None,
    )
    input_dto = SimpleNamespace(
        agent_id=agent.id,
        project_id=project_id,
        execution_context="production",
        snapshot_override=None,
        loaded_release_id=None,
        session_id=None,
        metadata=None,
    )
    resolver = object.__new__(ReleaseRuntimeResolver)

    resolved = await resolver._load_agent(uow, input_dto)

    assert resolved.settings["preserved"] == "value"
    assert resolved.settings["runtime_config"] == release_runtime_config
    assert resolved.settings["runtime_config"] is not release_runtime_config
