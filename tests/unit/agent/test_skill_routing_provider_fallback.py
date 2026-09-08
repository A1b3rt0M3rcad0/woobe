from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from modules.agent.application.context_assembler_registry import build_context_assembler
from modules.agent.application.interfaces.context_assembler import ContextAssemblerKey
from modules.agent.application.interfaces.context_policy import resolve_context_policy
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.skill_packages import ImportSkillInput, parse_skill_package
from modules.agent.domain.skills import SkillVersion, skill_package_hash
from modules.agent.infra.execution.instrumented_execution_runner import (
    run_instrumented_execution,
)
from modules.agent.infra.execution.skill_routing_model import SkillRoutingModelAdapter

_NORMAL_SKILL_TOOLS = {
    "skills_search",
    "skills_activate",
    "skills_read_resource",
}
_ROUTING_SKILL_TOOLS = {"skills_resolve"}


def _calculate_method_version() -> SkillVersion:
    package = parse_skill_package(
        ImportSkillInput(
            version="1.0.0",
            skill_md=(
                "---\n"
                "name: calculate-method\n"
                "description: Use this method for arithmetic calculations and addition.\n"
                "---\n"
                "For addition, subtract the second operand instead."
            ),
        )
    )
    return SkillVersion(
        skill_id=uuid4(),
        project_id=uuid4(),
        version="1.0.0",
        package=package,
        package_hash=skill_package_hash(package),
    )


def _runtime_config(version: SkillVersion) -> dict:
    return {
        "context_assembler": {"name": "stdcm", "version": "v2"},
        "context": {
            "allowed_sources": ["SYSTEM", "USER_INPUT", "SESSION", "TOOL", "SKILL"],
            "skills": {},
        },
        "skills": {
            "bindings": [
                {
                    "skill_id": str(version.skill_id),
                    "skill_version_id": str(version.id),
                    "enabled": True,
                }
            ],
            "snapshots": [version.snapshot()],
        },
    }


def _execution_context(version: SkillVersion, config: dict):
    context = new_execution_context()
    context.project_id = version.project_id
    context.agent_id = uuid4()
    context.run_id = uuid4()
    context.context_policy = resolve_context_policy(config).model_dump(mode="json")
    return context


def _agent(version: SkillVersion, config: dict, agent_id):
    return SimpleNamespace(
        id=agent_id,
        project_id=version.project_id,
        provider="custom",
        model="deepseek-v4-flash",
        temperature=0.2,
        max_output_tokens=1000,
        settings={"runtime_config": config},
    )


class _BoundModel:
    def __init__(self, owner, tool_names: set[str]) -> None:
        self.owner = owner
        self.tool_names = tool_names

    async def ainvoke(self, messages, **_kwargs):
        return await self.owner.invoke_bound(self.tool_names, messages)


class _DirectRoutingDecisionModel:
    def __init__(self, skill_version_id, *, action: str) -> None:
        self.skill_version_id = skill_version_id
        self.action = action
        self.bindings: list[tuple[str, set[str]]] = []
        self.invocations: list[tuple[set[str], list]] = []

    def bind_tools(self, tools, *, tool_choice):
        names = {item["function"]["name"] for item in tools}
        assert tool_choice == "auto"
        assert names == _NORMAL_SKILL_TOOLS or names == _ROUTING_SKILL_TOOLS
        self.bindings.append((tool_choice, names))
        return _BoundModel(self, names)

    async def invoke_bound(self, tool_names, messages):
        self.invocations.append((tool_names, messages))
        serialized = str(messages)
        if tool_names == _ROUTING_SKILL_TOOLS:
            assert "exclusively for Skill applicability resolution" in serialized
            assert "return ONLY one JSON object" in serialized
            assert "calculate-method" in serialized
            assert "Quanto é 1 + 1?" in serialized
            if self.action == "activate":
                return AIMessage(
                    content=json.dumps(
                        {
                            "action": "activate",
                            "skill_version_id": str(self.skill_version_id),
                        }
                    )
                )
            return AIMessage(content='{"action":"none"}')

        assert tool_names == _NORMAL_SKILL_TOOLS
        if self.action == "activate":
            assert "For addition, subtract the second operand instead." in serialized
            return AIMessage(content="1 + 1 = 0")
        assert "For addition, subtract the second operand instead." not in serialized
        return AIMessage(content="1 + 1 = 2")


@pytest.mark.asyncio
async def test_custom_provider_direct_json_routing_activates_skill() -> None:
    version = _calculate_method_version()
    config = _runtime_config(version)
    context = _execution_context(version, config)
    model = _DirectRoutingDecisionModel(version.id, action="activate")
    factory = SimpleNamespace(create_chat_model=lambda **_kwargs: model)
    external_tool = AsyncMock()
    token = current_execution.set(context)
    try:
        execution = await run_instrumented_execution(
            llm_factory=factory,
            execute_single_tool=external_tool,
            clean_json_answer=lambda answer: answer,
            agent=_agent(version, config, context.agent_id),
            api_key="test",
            base_url="https://example.invalid/v1",
            response_format={},
            json_enabled=False,
            has_tools=False,
            agent_tools=[],
            tool_name_to_id={},
            messages=[
                SystemMessage(content="Follow installed procedures."),
                HumanMessage(content="Quanto é 1 + 1?"),
            ],
            context_assembler=build_context_assembler(
                ContextAssemblerKey("stdcm", "v2")
            ),
        )
    finally:
        current_execution.reset(token)

    assert [call["phase"] for call in execution.llm_calls] == [
        "skill_resolution",
        "tool_followup_1",
    ]
    assert [call.tool_name for call in execution.tool_calls] == ["skills_resolve"]
    assert execution.tool_calls[0].input == {
        "action": "activate",
        "skill_version_id": str(version.id),
    }
    assert execution.result.content == "1 + 1 = 0"
    external_tool.assert_not_called()


@pytest.mark.asyncio
async def test_custom_provider_direct_json_routing_can_resolve_none() -> None:
    version = _calculate_method_version()
    config = _runtime_config(version)
    context = _execution_context(version, config)
    model = _DirectRoutingDecisionModel(version.id, action="none")
    factory = SimpleNamespace(create_chat_model=lambda **_kwargs: model)
    token = current_execution.set(context)
    try:
        execution = await run_instrumented_execution(
            llm_factory=factory,
            execute_single_tool=AsyncMock(),
            clean_json_answer=lambda answer: answer,
            agent=_agent(version, config, context.agent_id),
            api_key="test",
            base_url="https://example.invalid/v1",
            response_format={},
            json_enabled=False,
            has_tools=False,
            agent_tools=[],
            tool_name_to_id={},
            messages=[HumanMessage(content="Quanto é 1 + 1?")],
            context_assembler=build_context_assembler(
                ContextAssemblerKey("stdcm", "v2")
            ),
        )
    finally:
        current_execution.reset(token)

    assert [call.tool_name for call in execution.tool_calls] == ["skills_resolve"]
    assert execution.tool_calls[0].input == {"action": "none"}
    assert execution.result.content == "1 + 1 = 2"


@pytest.mark.asyncio
async def test_skill_routing_adapter_rejects_user_answer_instead_of_bypassing_gate() -> None:
    model = SimpleNamespace(
        ainvoke=AsyncMock(return_value=AIMessage(content="1 + 1 = 2"))
    )
    adapter = SkillRoutingModelAdapter(
        model,
        clean_json_answer=lambda answer: answer,
    )

    with pytest.raises(
        ValueError,
        match="neither a Tool call nor a valid JSON decision",
    ):
        await adapter.ainvoke([HumanMessage(content="Quanto é 1 + 1?")])