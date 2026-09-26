from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.tool_release_snapshots import tool_to_release_snapshot
from modules.agent.domain.entities import Agent, Tool
from modules.agent.domain.enums import RiskLevel, ToolStatus, ToolType
from modules.agent.infra.execution.ask_use_case import AskAgentUseCase
from modules.agent.infra.execution.explicit_runtime_persistence import (
    ExplicitRuntimePersistenceMixin,
)
from modules.agent.infra.execution.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)


def _tool(*, project_id, name="release_lookup"):
    return Tool(
        id=uuid4(),
        project_id=project_id,
        name=name,
        description="Lookup from immutable release snapshot",
        type=ToolType.HTTP,
        config={"url": "https://example.test/lookup", "method": "GET"},
        input_schema={"type": "object", "properties": {}},
        risk_level=RiskLevel.LOW,
        status=ToolStatus.ACTIVE,
    )


def _agent(*, project_id, runtime_config=None):
    settings = {}
    if runtime_config is not None:
        settings["runtime_config"] = runtime_config
    return Agent(
        id=uuid4(),
        project_id=project_id,
        name="runtime-agent",
        model="test-model",
        settings=settings,
    )


def _prepared(agent, *, definitions=None, mapping=None, has_tools=None, messages=None):
    definitions = list(definitions or [])
    mapping = dict(mapping or {})
    if has_tools is None:
        has_tools = bool(definitions)
    return (
        agent,
        None,
        uuid4(),
        "api-key",
        None,
        {},
        False,
        definitions,
        mapping,
        has_tools,
        [],
        list(messages or [HumanMessage(content="hello")]),
        [],
    )


def _definition(name):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Tool {name}",
            "parameters": {"type": "object", "properties": {}},
        },
    }


def _patch_lowest_prepare(monkeypatch, prepared):
    async def fake_prepare(_self, _input_dto):
        return prepared

    monkeypatch.setattr(AskAgentUseCase, "_prepare", fake_prepare)
    monkeypatch.setattr(ExplicitRuntimePersistenceMixin, "_prepare", fake_prepare)


def _use_case():
    use_case = StructuredOutputAskAgentUseCase.__new__(StructuredOutputAskAgentUseCase)
    use_case._session_factory = None
    use_case._encryption_key = "test-encryption-key"
    return use_case


async def _run_prepare(use_case, input_dto, context):
    token = current_execution.set(context)
    try:
        return await use_case._prepare(input_dto)
    finally:
        current_execution.reset(token)


@pytest.mark.asyncio
async def test_structured_runtime_preserves_exact_release_tool_selection_through_full_prepare(
    monkeypatch,
):
    project_id = uuid4()
    tool = _tool(project_id=project_id)
    snapshot = tool_to_release_snapshot(tool)
    agent = _agent(
        project_id=project_id,
        runtime_config={
            "tools": {
                "tool_ids": [str(tool.id)],
                "snapshots": [snapshot],
            }
        },
    )
    prepared = _prepared(agent)
    _patch_lowest_prepare(monkeypatch, prepared)
    context = new_execution_context()
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="use the lookup tool",
        execution_context="production",
    )

    result = await _run_prepare(_use_case(), input_dto, context)

    assert result[9] is True
    assert result[8] == {tool.name: str(tool.id)}
    assert len(result[7]) == 1
    assert context.tool_metadata["source"] == "release_snapshot"
    assert context.tool_metadata["tool_ids"] == [str(tool.id)]
    assert str(tool.id) in context.tool_snapshots


@pytest.mark.asyncio
async def test_tool_enabled_prepare_keeps_grounding_invocation_scoped(monkeypatch):
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    tool_id = uuid4()
    prepared = _prepared(
        agent,
        definitions=[_definition("lookup")],
        mapping={"lookup": str(tool_id)},
        has_tools=True,
    )
    _patch_lowest_prepare(monkeypatch, prepared)
    context = new_execution_context()
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="hello",
    )

    result = await _run_prepare(_use_case(), input_dto, context)

    assert result[9] is True
    assert result[8] == {"lookup": str(tool_id)}
    assert len(result[7]) == 1
    assert isinstance(result[11][-1], HumanMessage)
    assert not any(
        isinstance(message, SystemMessage) and "Tool grounding rules" in message.content
        for message in result[11]
    )


@pytest.mark.asyncio
async def test_internal_network_tool_is_added_without_replacing_agent_tools(monkeypatch):
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    agent_tool_id = uuid4()
    internal_tool_id = uuid4()
    prepared = _prepared(
        agent,
        definitions=[_definition("agent_lookup")],
        mapping={"agent_lookup": str(agent_tool_id)},
        has_tools=True,
    )
    _patch_lowest_prepare(monkeypatch, prepared)
    context = new_execution_context()
    context.internal_tool_definitions = [_definition("delegate_child")]
    context.internal_tool_name_to_id = {"delegate_child": str(internal_tool_id)}
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="delegate if needed",
        metadata={"source": "network_runtime"},
    )

    result = await _run_prepare(_use_case(), input_dto, context)

    assert result[9] is True
    assert len(result[7]) == 2
    assert result[8] == {
        "agent_lookup": str(agent_tool_id),
        "delegate_child": str(internal_tool_id),
    }


@pytest.mark.asyncio
async def test_internal_network_tool_name_collision_fails_deterministically(monkeypatch):
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    prepared = _prepared(
        agent,
        definitions=[_definition("lookup")],
        mapping={"lookup": str(uuid4())},
        has_tools=True,
    )
    _patch_lowest_prepare(monkeypatch, prepared)
    context = new_execution_context()
    context.internal_tool_definitions = [_definition("lookup")]
    context.internal_tool_name_to_id = {"lookup": str(uuid4())}
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="hello",
        metadata={"source": "network_runtime"},
    )

    with pytest.raises(ValueError, match="collides with an Agent Tool"):
        await _run_prepare(_use_case(), input_dto, context)


@pytest.mark.asyncio
async def test_prepare_without_tools_does_not_inject_tool_grounding_rules(monkeypatch):
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    prepared = _prepared(agent, definitions=[], mapping={}, has_tools=False)
    _patch_lowest_prepare(monkeypatch, prepared)
    context = new_execution_context()
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="hello",
    )

    result = await _run_prepare(_use_case(), input_dto, context)

    assert result[9] is False
    assert not any(
        isinstance(message, SystemMessage) and "Tool grounding rules" in message.content
        for message in result[11]
    )


@pytest.mark.asyncio
async def test_release_snapshot_and_internal_delegation_coexist_in_network_runtime(
    monkeypatch,
):
    project_id = uuid4()
    tool = _tool(project_id=project_id, name="release_tool")
    snapshot = tool_to_release_snapshot(tool)
    agent = _agent(
        project_id=project_id,
        runtime_config={
            "tools": {
                "tool_ids": [str(tool.id)],
                "snapshots": [snapshot],
            }
        },
    )
    prepared = _prepared(agent)
    _patch_lowest_prepare(monkeypatch, prepared)
    context = new_execution_context()
    delegate_id = uuid4()
    context.internal_tool_definitions = [_definition("delegate_child")]
    context.internal_tool_name_to_id = {"delegate_child": str(delegate_id)}
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="run network",
        execution_context="production",
        metadata={"source": "network_runtime"},
    )

    result = await _run_prepare(_use_case(), input_dto, context)

    assert result[9] is True
    assert result[8] == {
        tool.name: str(tool.id),
        "delegate_child": str(delegate_id),
    }
    assert context.tool_metadata["source"] == "release_snapshot"
    assert str(tool.id) in context.tool_snapshots
