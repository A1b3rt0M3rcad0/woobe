from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from modules.agent.application.context_assembler_registry import build_context_assembler
from modules.agent.application.interfaces.context_assembler import ContextAssemblerKey
from modules.agent.application.interfaces.context_policy import (
    SkillContextPolicy,
    resolve_context_policy,
)
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.skill_bindings import frozen_enabled_skills
from modules.agent.application.skill_packages import ImportSkillInput, parse_skill_package
from modules.agent.application.skill_runtime import SkillRuntime
from modules.agent.domain.skills import SkillVersion, skill_package_hash
from modules.agent.infra.execution.instrumented_execution_runner import (
    configure_skill_runtime,
    run_instrumented_execution,
)

_COMPLETE_SKILL_TOOLS = {
    "skills_activate",
    "skills_read_resource",
}
_INCOMPLETE_SKILL_TOOLS = {
    "skills_search",
    "skills_activate",
    "skills_read_resource",
}


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
        "context_assembler": {"name": "stdcm"},
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


def _agent(version: SkillVersion, config: dict, agent_id, *, provider: str = "openai"):
    return SimpleNamespace(
        id=agent_id,
        project_id=version.project_id,
        provider=provider,
        model="test",
        temperature=0.2,
        max_output_tokens=1000,
        settings={"runtime_config": config},
    )


def _tool_names(runtime: SkillRuntime) -> set[str]:
    return {item["function"]["name"] for item in runtime.definitions}


def _configure_skill_runtime() -> None:
    configure_skill_runtime(frozen_enabled_skills, SkillRuntime)


def test_installed_catalog_exposes_only_routing_metadata() -> None:
    version = _calculate_method_version()
    runtime = SkillRuntime([version.snapshot()], SkillContextPolicy(), set())

    contributions = runtime.contributions()
    assert len(contributions) == 1

    catalog = contributions[0]["content"]
    assert '"catalog_complete":true' in catalog
    assert '"name":"calculate-method"' in catalog
    assert '"version":"1.0.0"' in catalog
    assert f'"skill_version_id":"{version.id}"' in catalog
    assert (
        '"when_to_use":"Use this method for arithmetic calculations and addition."'
        in catalog
    )
    assert version.package["instructions"] not in catalog
    assert '"required_tools"' not in catalog
    assert '"description"' not in catalog
    assert runtime.catalog_complete is True
    assert _tool_names(runtime) == _COMPLETE_SKILL_TOOLS


def test_complete_catalog_does_not_publish_or_execute_search() -> None:
    version = _calculate_method_version()
    runtime = SkillRuntime([version.snapshot()], SkillContextPolicy(), set())

    assert "skills_search" not in _tool_names(runtime)
    result = runtime.execute(
        "skills_search",
        {"query": "arithmetic"},
        tool_call_id="search",
    )

    assert result["success"] is False
    assert "catalog is complete" in result["error"]
    assert len(runtime.contributions()) == 1


def test_legacy_skill_resolve_is_reserved_but_not_executable() -> None:
    version = _calculate_method_version()
    runtime = SkillRuntime([version.snapshot()], SkillContextPolicy(), set())

    assert "skills_resolve" in runtime.mapping
    assert "skills_resolve" not in _tool_names(runtime)
    result = runtime.execute(
        "skills_resolve",
        {"action": "none"},
        tool_call_id="legacy",
    )

    assert result["success"] is False
    assert "legacy Skill operation" in result["error"]
    assert version.package["instructions"] not in str(runtime.contributions())


def test_large_catalog_preserves_visible_metadata_and_enables_search() -> None:
    version = _calculate_method_version()
    snapshots = []
    for index in range(12):
        snapshot = deepcopy(version.snapshot())
        snapshot["skill_id"] = str(uuid4())
        snapshot["skill_version_id"] = str(uuid4())
        snapshot["package"]["name"] = f"calculate-method-{index:02d}"
        snapshot["package"]["description"] = (
            f"Use arithmetic calculation method variant {index}."
        )
        snapshots.append(snapshot)

    runtime = SkillRuntime(
        snapshots,
        SkillContextPolicy(catalog_max_units=256, search_limit=3),
        set(),
    )

    catalog_text = runtime.contributions()[0]["content"]
    payload = json.loads(catalog_text.split("\n", 1)[1])
    assert payload["catalog_complete"] is False
    assert payload["installed_count"] == 12
    assert payload["visible_count"] == len(payload["skills"])
    assert payload["omitted_count"] == 12 - payload["visible_count"]
    assert 0 < payload["visible_count"] < 12
    assert runtime.catalog_complete is False
    assert _tool_names(runtime) == _INCOMPLETE_SKILL_TOOLS

    result = runtime.execute(
        "skills_search",
        {"query": "calculate arithmetic", "offset": 0},
        tool_call_id="search",
    )

    assert result["success"] is True
    assert result["output"]["installed_count"] == 12
    assert result["output"]["matched_count"] == 12
    assert result["output"]["result_mode"] == "matched"
    assert 1 <= len(result["output"]["skills"]) <= 3


def test_activated_instructions_are_discarded_when_next_run_runtime_is_created() -> None:
    version = _calculate_method_version()
    first_run = SkillRuntime([version.snapshot()], SkillContextPolicy(), set())

    activation = first_run.execute(
        "skills_activate",
        {"skill_version_id": str(version.id)},
        tool_call_id="activate",
    )
    assert activation["success"] is True
    assert version.package["instructions"] in str(first_run.contributions())

    next_run = SkillRuntime([version.snapshot()], SkillContextPolicy(), set())
    assert len(next_run.contributions()) == 1
    assert version.package["instructions"] not in str(next_run.contributions())
    assert "when_to_use" in next_run.contributions()[0]["content"]


class _BoundModel:
    def __init__(self, owner, tool_names: set[str]) -> None:
        self.owner = owner
        self.tool_names = tool_names

    async def ainvoke(self, messages, **_kwargs):
        return await self.owner.invoke_bound(self.tool_names, messages)


class _DemandDrivenActivationModel:
    def __init__(self, skill_version_id) -> None:
        self.skill_version_id = skill_version_id
        self.bindings: list[tuple[str, set[str]]] = []
        self.invocations = []

    def bind_tools(self, tools, *, tool_choice):
        names = {item["function"]["name"] for item in tools}
        assert tool_choice == "auto"
        assert names == _COMPLETE_SKILL_TOOLS
        self.bindings.append((tool_choice, names))
        return _BoundModel(self, names)

    async def invoke_bound(self, tool_names, messages):
        assert tool_names == _COMPLETE_SKILL_TOOLS
        self.invocations.append(messages)
        serialized = str(messages)
        assert "calculate-method" in serialized
        assert "when_to_use" in serialized
        assert str(self.skill_version_id) in serialized
        assert "skills_resolve" not in serialized
        if len(self.invocations) == 1:
            assert "Quanto é 1 + 1?" in serialized
            assert "answer directly without any Skill operation" in serialized
            assert "For addition, subtract the second operand instead." not in serialized
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "skills_activate",
                        "args": {"skill_version_id": str(self.skill_version_id)},
                        "id": "activate",
                        "type": "tool_call",
                    }
                ],
            )
        assert "For addition, subtract the second operand instead." in serialized
        return AIMessage(content="1 + 1 = 0")


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "custom"])
async def test_visible_skill_is_activated_directly_from_normal_model_call(provider) -> None:
    _configure_skill_runtime()
    version = _calculate_method_version()
    config = _runtime_config(version)
    context = _execution_context(version, config)

    model = _DemandDrivenActivationModel(version.id)
    factory = SimpleNamespace(create_chat_model=lambda **_kwargs: model)
    agent = _agent(version, config, context.agent_id, provider=provider)
    external_tool = AsyncMock()
    token = current_execution.set(context)
    try:
        execution = await run_instrumented_execution(
            llm_factory=factory,
            execute_single_tool=external_tool,
            clean_json_answer=lambda answer: answer,
            agent=agent,
            api_key="test",
            base_url="https://example.invalid/v1" if provider == "custom" else None,
            response_format={},
            json_enabled=False,
            has_tools=False,
            agent_tools=[],
            tool_name_to_id={},
            messages=[
                SystemMessage(content="Follow installed procedures."),
                HumanMessage(content="Quanto é 5 + 5?"),
                AIMessage(content="10"),
                HumanMessage(content="Quanto é 1 + 1?"),
            ],
            context_assembler=build_context_assembler(
                ContextAssemblerKey("stdcm")
            ),
        )
    finally:
        current_execution.reset(token)

    assert model.bindings == [("auto", _COMPLETE_SKILL_TOOLS)]
    assert len(model.invocations) == 2
    assert [call["phase"] for call in execution.llm_calls] == [
        "capability_response_generation",
        "tool_followup_1",
    ]
    assert [call.tool_name for call in execution.tool_calls] == ["skills_activate"]
    assert execution.result.content == "1 + 1 = 0"
    external_tool.assert_not_called()


class _UnrelatedCurrentRequestModel:
    def __init__(self) -> None:
        self.bindings: list[tuple[str, set[str]]] = []
        self.invocations = []

    def bind_tools(self, tools, *, tool_choice):
        names = {item["function"]["name"] for item in tools}
        assert tool_choice == "auto"
        assert names == _COMPLETE_SKILL_TOOLS
        self.bindings.append((tool_choice, names))
        return _BoundModel(self, names)

    async def invoke_bound(self, tool_names, messages):
        assert tool_names == _COMPLETE_SKILL_TOOLS
        self.invocations.append(messages)
        serialized = str(messages)
        assert "calculate-method" in serialized
        assert "when_to_use" in serialized
        assert "Como se vai?" in serialized
        assert "I used calculate-method for the previous arithmetic request." in serialized
        assert "never activate a Skill solely because" in serialized
        assert "For addition, subtract the second operand instead." not in serialized
        return AIMessage(content="Vou bem, obrigado. E você?")


@pytest.mark.asyncio
async def test_unrelated_request_answers_directly_without_skill_operation() -> None:
    _configure_skill_runtime()
    version = _calculate_method_version()
    config = _runtime_config(version)
    context = _execution_context(version, config)

    model = _UnrelatedCurrentRequestModel()
    factory = SimpleNamespace(create_chat_model=lambda **_kwargs: model)
    agent = _agent(version, config, context.agent_id)
    token = current_execution.set(context)
    try:
        execution = await run_instrumented_execution(
            llm_factory=factory,
            execute_single_tool=AsyncMock(),
            clean_json_answer=lambda answer: answer,
            agent=agent,
            api_key="test",
            base_url=None,
            response_format={},
            json_enabled=False,
            has_tools=False,
            agent_tools=[],
            tool_name_to_id={},
            messages=[
                SystemMessage(content="Follow installed procedures."),
                HumanMessage(content="Quanto é 1 + 1?"),
                AIMessage(
                    content="I used calculate-method for the previous arithmetic request."
                ),
                HumanMessage(content="Como se vai?"),
            ],
            context_assembler=build_context_assembler(
                ContextAssemblerKey("stdcm")
            ),
        )
    finally:
        current_execution.reset(token)

    assert model.bindings == [("auto", _COMPLETE_SKILL_TOOLS)]
    assert len(model.invocations) == 1
    assert [call["phase"] for call in execution.llm_calls] == [
        "capability_response_generation"
    ]
    assert execution.tool_calls == []
    assert execution.result.content == "Vou bem, obrigado. E você?"


class _DirectModel:
    def __init__(self) -> None:
        self.invocations = []

    def bind_tools(self, _tools, *, tool_choice):
        raise AssertionError(
            f"Agent without enabled Skills or Tools must not bind capabilities: {tool_choice}"
        )

    async def ainvoke(self, messages, **_kwargs):
        self.invocations.append(messages)
        return AIMessage(content="5 + 5 = 10")


@pytest.mark.asyncio
async def test_agent_without_enabled_skills_has_no_extra_model_round() -> None:
    model = _DirectModel()
    factory = SimpleNamespace(create_chat_model=lambda **_kwargs: model)
    agent = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        provider="openai",
        model="test",
        temperature=0.2,
        max_output_tokens=1000,
        settings={},
    )

    execution = await run_instrumented_execution(
        llm_factory=factory,
        execute_single_tool=AsyncMock(),
        clean_json_answer=lambda answer: answer,
        agent=agent,
        api_key="test",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=False,
        agent_tools=[],
        tool_name_to_id={},
        messages=[HumanMessage(content="Quanto é 5 + 5?")],
    )

    assert len(model.invocations) == 1
    assert [call["phase"] for call in execution.llm_calls] == ["response_generation"]
    assert execution.tool_calls == []
    assert execution.result.content == "5 + 5 = 10"
