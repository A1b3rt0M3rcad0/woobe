from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.runtime_tool_inventory import RUNTIME_TOOL_INVENTORY_NAME
from modules.agent.application.tool_release_snapshots import tool_to_release_snapshot
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.runtime.release_runtime_resolver import (
    ReleaseRuntimeResolver,
)
from modules.agent.domain.entities import Agent, Tool
from modules.agent.domain.enums import RiskLevel, ToolStatus, ToolType
from shared.infra.errors import ValidationError


def _tool(*, project_id, name="lookup_order", status=ToolStatus.ACTIVE, agent_id=None):
    return Tool(
        id=uuid4(),
        project_id=project_id,
        agent_id=agent_id,
        name=name,
        description=f"Tool {name}",
        type=ToolType.HTTP,
        config={"url": f"https://example.test/{name}", "method": "GET"},
        input_schema={"type": "object", "properties": {}},
        risk_level=RiskLevel.LOW,
        status=status,
    )


def _agent(*, project_id, tools_config=None):
    runtime_config = {} if tools_config is None else {"tools": tools_config}
    return Agent(
        id=uuid4(),
        project_id=project_id,
        name="runtime-agent",
        model="test-model",
        settings={"runtime_config": runtime_config},
    )


def _prepared(agent):
    return (
        agent,
        None,
        uuid4(),
        "api-key",
        None,
        {},
        False,
        [],
        {},
        False,
        [],
        [],
        [],
    )


def _resolver(reader=None):
    resolver = ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)
    if reader is not None:
        resolver.configure_runtime_tool_reader(reader)
    return resolver


async def _apply(resolver, prepared):
    context = new_execution_context()
    token = current_execution.set(context)
    try:
        result = await resolver._apply_runtime_tool_selection(prepared)
        return result, context
    finally:
        current_execution.reset(token)


@pytest.mark.asyncio
async def test_runtime_without_runtime_config_keeps_existing_tool_contract():
    project_id = uuid4()
    agent = Agent(id=uuid4(), project_id=project_id, model="test-model", settings={})
    prepared = _prepared(agent)

    result, context = await _apply(_resolver(), prepared)

    assert result is prepared
    assert context.tool_metadata is None
    assert context.tool_snapshots is None


@pytest.mark.asyncio
async def test_runtime_without_tools_config_keeps_existing_tool_contract():
    project_id = uuid4()
    agent = Agent(
        id=uuid4(),
        project_id=project_id,
        model="test-model",
        settings={"runtime_config": {"rag": {"top_k": 5}}},
    )
    prepared = _prepared(agent)

    result, context = await _apply(_resolver(), prepared)

    assert result is prepared
    assert context.tool_metadata is None


@pytest.mark.asyncio
async def test_draft_selected_project_tool_is_exposed_even_without_agent_fk():
    project_id = uuid4()
    tool = _tool(project_id=project_id, agent_id=None)
    agent = _agent(
        project_id=project_id,
        tools_config={"tool_ids": [str(tool.id)]},
    )
    reader = AsyncMock(return_value=[tool])

    result, context = await _apply(_resolver(reader), _prepared(agent))

    reader.assert_awaited_once_with([tool.id])
    assert result[9] is True
    assert len(result[7]) == 2
    assert result[8][tool.name] == str(tool.id)
    assert RUNTIME_TOOL_INVENTORY_NAME in result[8]
    assert context.tool_metadata["source"] == "draft_live"
    assert context.tool_metadata["tool_ids"] == [str(tool.id)]
    assert str(tool.id) in context.tool_snapshots


@pytest.mark.asyncio
async def test_selected_tool_order_is_stable_and_duplicate_ids_are_removed():
    project_id = uuid4()
    first = _tool(project_id=project_id, name="first_tool")
    second = _tool(project_id=project_id, name="second_tool")
    agent = _agent(
        project_id=project_id,
        tools_config={
            "tool_ids": [str(first.id), str(first.id), str(second.id)],
        },
    )
    reader = AsyncMock(return_value=[second, first])

    result, context = await _apply(_resolver(reader), _prepared(agent))

    reader.assert_awaited_once_with([first.id, second.id])
    assert context.tool_metadata["tool_ids"] == [str(first.id), str(second.id)]
    assert list(result[8]) == [first.name, second.name, RUNTIME_TOOL_INVENTORY_NAME]


@pytest.mark.asyncio
async def test_selected_live_tool_must_exist():
    project_id = uuid4()
    missing_id = uuid4()
    agent = _agent(
        project_id=project_id,
        tools_config={"tool_ids": [str(missing_id)]},
    )

    with pytest.raises(ValidationError, match="Selected tool was not found"):
        await _apply(_resolver(AsyncMock(return_value=[])), _prepared(agent))


@pytest.mark.asyncio
async def test_selected_live_tool_must_belong_to_agent_project():
    project_id = uuid4()
    tool = _tool(project_id=uuid4())
    agent = _agent(
        project_id=project_id,
        tools_config={"tool_ids": [str(tool.id)]},
    )

    with pytest.raises(ValidationError, match="does not belong to this Project"):
        await _apply(_resolver(AsyncMock(return_value=[tool])), _prepared(agent))


@pytest.mark.asyncio
async def test_selected_live_tool_must_be_active():
    project_id = uuid4()
    tool = _tool(project_id=project_id, status=ToolStatus.INACTIVE)
    agent = _agent(
        project_id=project_id,
        tools_config={"tool_ids": [str(tool.id)]},
    )

    with pytest.raises(ValidationError, match="Selected tool is not active"):
        await _apply(_resolver(AsyncMock(return_value=[tool])), _prepared(agent))


@pytest.mark.asyncio
async def test_live_tool_selection_requires_runtime_reader():
    project_id = uuid4()
    tool_id = uuid4()
    agent = _agent(
        project_id=project_id,
        tools_config={"tool_ids": [str(tool_id)]},
    )

    with pytest.raises(ValidationError, match="runtime reader is not configured"):
        await _apply(_resolver(), _prepared(agent))


@pytest.mark.asyncio
async def test_release_snapshot_is_exposed_without_live_repository_reader():
    project_id = uuid4()
    tool = _tool(project_id=project_id)
    snapshot = tool_to_release_snapshot(tool)
    agent = _agent(
        project_id=project_id,
        tools_config={
            "tool_ids": [str(tool.id)],
            "snapshots": [snapshot],
        },
    )

    result, context = await _apply(_resolver(), _prepared(agent))

    assert result[9] is True
    assert result[8][tool.name] == str(tool.id)
    assert RUNTIME_TOOL_INVENTORY_NAME in result[8]
    assert context.tool_metadata["source"] == "release_snapshot"
    assert context.tool_metadata["tool_ids"] == [str(tool.id)]
    assert context.tool_snapshots[str(tool.id)]["snapshot_hash"] == snapshot["snapshot_hash"]


@pytest.mark.asyncio
async def test_snapshot_only_configuration_derives_selected_tool_ids():
    project_id = uuid4()
    tool = _tool(project_id=project_id)
    snapshot = tool_to_release_snapshot(tool)
    agent = _agent(
        project_id=project_id,
        tools_config={"snapshots": [snapshot]},
    )

    result, context = await _apply(_resolver(), _prepared(agent))

    assert result[9] is True
    assert context.tool_metadata["tool_ids"] == [str(tool.id)]
    assert context.tool_metadata["source"] == "release_snapshot"


@pytest.mark.asyncio
async def test_release_snapshot_must_belong_to_agent_project():
    project_id = uuid4()
    tool = _tool(project_id=uuid4())
    snapshot = tool_to_release_snapshot(tool)
    agent = _agent(
        project_id=project_id,
        tools_config={
            "tool_ids": [str(tool.id)],
            "snapshots": [snapshot],
        },
    )

    with pytest.raises(ValidationError, match="snapshot does not belong to this Project"):
        await _apply(_resolver(), _prepared(agent))


@pytest.mark.asyncio
async def test_release_snapshot_must_be_active():
    project_id = uuid4()
    tool = _tool(project_id=project_id, status=ToolStatus.INACTIVE)
    snapshot = tool_to_release_snapshot(tool)
    agent = _agent(
        project_id=project_id,
        tools_config={
            "tool_ids": [str(tool.id)],
            "snapshots": [snapshot],
        },
    )

    with pytest.raises(ValidationError, match="snapshot is not active"):
        await _apply(_resolver(), _prepared(agent))


@pytest.mark.asyncio
async def test_hybrid_runtime_preserves_snapshot_and_live_tool_in_one_contract():
    project_id = uuid4()
    snapshotted = _tool(project_id=project_id, name="snapshotted_tool")
    live = _tool(project_id=project_id, name="live_tool")
    snapshot = tool_to_release_snapshot(snapshotted)
    agent = _agent(
        project_id=project_id,
        tools_config={
            "tool_ids": [str(snapshotted.id), str(live.id)],
            "snapshots": [snapshot],
        },
    )
    reader = AsyncMock(return_value=[live])

    result, context = await _apply(_resolver(reader), _prepared(agent))

    reader.assert_awaited_once_with([live.id])
    assert result[9] is True
    assert set(result[8]) == {
        snapshotted.name,
        live.name,
        RUNTIME_TOOL_INVENTORY_NAME,
    }
    assert context.tool_metadata["source"] == "hybrid_snapshot"
    assert context.tool_metadata["tool_ids"] == [str(snapshotted.id), str(live.id)]


@pytest.mark.asyncio
async def test_permission_override_is_part_of_runtime_tool_provenance():
    project_id = uuid4()
    tool = _tool(project_id=project_id)
    permissions = {str(tool.id): {"allow_local_network": True}}
    agent = _agent(
        project_id=project_id,
        tools_config={
            "tool_ids": [str(tool.id)],
            "permissions": permissions,
        },
    )

    _, context = await _apply(
        _resolver(AsyncMock(return_value=[tool])),
        _prepared(agent),
    )

    assert context.tool_metadata["permission_overrides"] == permissions
    assert str(tool.id) in context.tool_snapshots


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "snapshots, message",
    [
        ({}, "invalid tool snapshots"),
        (["not-a-snapshot"], "invalid tool snapshot"),
        ([{"name": "missing-id"}], "snapshot id is missing"),
    ],
)
async def test_malformed_release_snapshot_contract_is_rejected(snapshots, message):
    project_id = uuid4()
    agent = _agent(
        project_id=project_id,
        tools_config={"snapshots": snapshots},
    )

    with pytest.raises(ValidationError, match=message):
        await _apply(_resolver(), _prepared(agent))


@pytest.mark.asyncio
async def test_invalid_selected_tool_id_is_rejected_before_repository_access():
    project_id = uuid4()
    reader = AsyncMock()
    agent = _agent(
        project_id=project_id,
        tools_config={"tool_ids": ["not-a-uuid"]},
    )

    with pytest.raises(ValidationError, match="invalid tool id"):
        await _apply(_resolver(reader), _prepared(agent))

    reader.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_tool_selection_explicitly_produces_no_tools_with_provenance():
    project_id = uuid4()
    agent = _agent(project_id=project_id, tools_config={"tool_ids": []})

    result, context = await _apply(_resolver(), _prepared(agent))

    assert result[7] == []
    assert result[8] == {}
    assert result[9] is False
    assert context.tool_snapshots is None
    assert context.tool_metadata["source"] == "draft_live"
    assert context.tool_metadata["tool_ids"] == []