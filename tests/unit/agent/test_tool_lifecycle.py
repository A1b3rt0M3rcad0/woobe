from uuid import uuid4

import pytest

from modules.agent.application.dtos.tools_dtos import DeleteToolInput
from modules.agent.application.tool_release_snapshots import (
    build_release_tool_runtime,
    tool_from_release_snapshot,
    tool_to_release_snapshot,
)
from modules.agent.application.interfaces.execution_context import current_execution, new_execution_context
from modules.agent.infra.execution.release_runtime_resolver import ReleaseRuntimeResolver
from modules.agent.application.use_cases.tools_use_cases import (
    DeleteToolUseCase,
    GetToolUsageImpactUseCase,
)
from modules.agent.domain.entities import Agent, AgentRelease, Tool
from modules.agent.domain.enums import ReleaseStatus, ToolStatus, ToolType
from modules.agent.domain.errors import ToolInUseError, ToolNotFoundError
from shared.infra.errors import ValidationError


class FakeToolRepository:
    def __init__(self, tools: list[Tool]) -> None:
        self.tools = {tool.id: tool for tool in tools}
        self.deleted: list = []

    async def get_by_id(self, tool_id):
        tool = self.tools.get(tool_id)
        if tool is None:
            raise ToolNotFoundError(tool_id)
        return tool

    async def delete(self, tool_id):
        if tool_id not in self.tools:
            raise ToolNotFoundError(tool_id)
        self.deleted.append(tool_id)
        del self.tools[tool_id]


class FakeAgentRepository:
    def __init__(self, agents: list[Agent]) -> None:
        self.agents = agents

    async def list_by_project(self, project_id):
        return [agent for agent in self.agents if agent.project_id == project_id]

    async def get_by_id(self, agent_id):
        return next((agent for agent in self.agents if agent.id == agent_id), None)


class FakeReleaseRepository:
    def __init__(self, releases: list[AgentRelease]) -> None:
        self.releases = releases

    async def list_by_agent(self, agent_id):
        return [release for release in self.releases if release.agent_id == agent_id]

    async def list_by_status(self, agent_id, status):
        status_value = getattr(status, "value", status)
        return [
            release
            for release in self.releases
            if release.agent_id == agent_id
            and getattr(release.status, "value", release.status) == status_value
        ]


def make_mcp_tool(*, project_id=None, status=ToolStatus.ACTIVE, name="provider") -> Tool:
    return Tool(
        id=uuid4(),
        project_id=project_id or uuid4(),
        name=name,
        type=ToolType.MCP,
        status=status,
        config={
            "protocol": "mcp",
            "mode": "server",
            "exposure": "all_discovered",
            "server": {"transport": "streamable_http", "url": "https://example.com/mcp"},
            "discovered_tools": [
                {"name": "search", "permission": {"mode": "review"}},
            ],
        },
    )


def make_release(agent: Agent, status: ReleaseStatus, tool: Tool) -> AgentRelease:
    return AgentRelease(
        project_id=agent.project_id,
        agent_id=agent.id,
        status=status,
        runtime_config={
            "tools": {
                "tool_ids": [str(tool.id)],
                "snapshots": [tool_to_release_snapshot(tool)],
            }
        },
    )


@pytest.mark.asyncio
async def test_usage_impact_counts_current_and_historical_agent_versions():
    project_id = uuid4()
    tool = make_mcp_tool(project_id=project_id)
    agent_a = Agent(project_id=project_id, model="test-model")
    agent_b = Agent(project_id=project_id, model="test-model")
    releases = [
        make_release(agent_a, ReleaseStatus.draft, tool),
        make_release(agent_a, ReleaseStatus.staging, tool),
        make_release(agent_b, ReleaseStatus.production, tool),
        make_release(agent_b, ReleaseStatus.archived, tool),
    ]

    use_case = GetToolUsageImpactUseCase(
        FakeToolRepository([tool]),
        FakeAgentRepository([agent_a, agent_b]),
        FakeReleaseRepository(releases),
    )

    impact = await use_case.execute(tool.id)

    assert impact.in_use is True
    assert impact.can_delete is False
    assert impact.can_retire is True
    assert impact.draft_agents == 1
    assert impact.staging_agents == 1
    assert impact.production_agents == 1
    assert impact.historical_releases == 1
    assert impact.total_references == 4


@pytest.mark.asyncio
async def test_delete_rejects_referenced_tool():
    project_id = uuid4()
    tool = make_mcp_tool(project_id=project_id)
    agent = Agent(project_id=project_id, model="test-model")
    tool_repo = FakeToolRepository([tool])
    use_case = DeleteToolUseCase(
        tool_repo,
        FakeAgentRepository([agent]),
        FakeReleaseRepository([make_release(agent, ReleaseStatus.production, tool)]),
    )

    with pytest.raises(ToolInUseError) as exc_info:
        await use_case.execute(DeleteToolInput(tool_id=tool.id))

    assert exc_info.value.impact.production_agents == 1
    assert tool_repo.deleted == []


@pytest.mark.asyncio
async def test_delete_allows_unreferenced_tool():
    project_id = uuid4()
    tool = make_mcp_tool(project_id=project_id)
    tool_repo = FakeToolRepository([tool])
    use_case = DeleteToolUseCase(
        tool_repo,
        FakeAgentRepository([]),
        FakeReleaseRepository([]),
    )

    await use_case.execute(DeleteToolInput(tool_id=tool.id))

    assert tool_repo.deleted == [tool.id]


@pytest.mark.asyncio
async def test_save_draft_reuses_previous_snapshot_for_retired_tool():
    tool = make_mcp_tool()
    previous_snapshot = tool_to_release_snapshot(tool)
    tool.status = ToolStatus.DEPRECATED
    repo = FakeToolRepository([tool])

    runtime = await build_release_tool_runtime(
        repo,
        project_id=tool.project_id,
        raw_tool_ids=[str(tool.id)],
        raw_permissions={str(tool.id): {"search": {"mode": "allow"}}},
        previous_snapshots=[previous_snapshot],
    )

    restored = tool_from_release_snapshot(runtime["snapshots"][0])
    assert restored.status == ToolStatus.ACTIVE
    assert restored.config["discovered_tools"][0]["permission"]["mode"] == "allow"
    assert tool.status == ToolStatus.DEPRECATED


@pytest.mark.asyncio
async def test_new_binding_to_retired_tool_is_rejected_without_previous_snapshot():
    tool = make_mcp_tool(status=ToolStatus.DEPRECATED)

    with pytest.raises(ValidationError, match="not active"):
        await build_release_tool_runtime(
            FakeToolRepository([tool]),
            project_id=tool.project_id,
            raw_tool_ids=[str(tool.id)],
        )


@pytest.mark.asyncio
async def test_runtime_resolves_saved_snapshot_and_new_live_tool_together():
    project_id = uuid4()
    saved_tool = make_mcp_tool(project_id=project_id, name="saved")
    new_tool = make_mcp_tool(project_id=project_id, name="new")
    saved_snapshot = tool_to_release_snapshot(saved_tool)
    agent = Agent(
        project_id=project_id,
        model="test-model",
        settings={
            "runtime_config": {
                "tools": {
                    "tool_ids": [str(saved_tool.id), str(new_tool.id)],
                    "snapshots": [saved_snapshot],
                    "permissions": {
                        str(saved_tool.id): {"search": {"mode": "allow"}},
                        str(new_tool.id): {"search": {"mode": "deny"}},
                    },
                }
            }
        },
    )

    async def read_runtime_tools(tool_ids):
        assert tool_ids == [new_tool.id]
        return [new_tool]

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
    assert context.tool_metadata["source"] == "hybrid_snapshot"
    assert context.tool_snapshots is not None
    assert set(context.tool_snapshots) == {str(saved_tool.id), str(new_tool.id)}
    assert updated[9] is True


@pytest.mark.asyncio
async def test_unsaved_playground_runtime_merges_current_draft_snapshots_by_selected_tool_id():
    project_id = uuid4()
    saved_tool = make_mcp_tool(project_id=project_id)
    removed_tool = make_mcp_tool(project_id=project_id)
    new_tool = make_mcp_tool(project_id=project_id)
    agent = Agent(project_id=project_id, model="test-model")
    draft = AgentRelease(
        project_id=project_id,
        agent_id=agent.id,
        status=ReleaseStatus.draft,
        runtime_config={
            "tools": {
                "tool_ids": [str(saved_tool.id), str(removed_tool.id)],
                "snapshots": [
                    tool_to_release_snapshot(saved_tool),
                    tool_to_release_snapshot(removed_tool),
                ],
            }
        },
    )
    resolver = object.__new__(ReleaseRuntimeResolver)
    override_runtime = {
        "tools": {
            "tool_ids": [str(saved_tool.id), str(new_tool.id)],
            "permissions": {str(saved_tool.id): {"search": {"mode": "allow"}}},
        }
    }

    merged = await resolver._merge_playground_runtime_config(
        FakeReleaseRepository([draft]),
        agent.id,
        override_runtime,
    )

    merged_snapshots = merged["tools"]["snapshots"]
    assert [snapshot["id"] for snapshot in merged_snapshots] == [str(saved_tool.id)]
    assert merged is not override_runtime
