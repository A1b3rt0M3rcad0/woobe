from __future__ import annotations

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
from modules.agent.application.skill_packages import ImportSkillInput, parse_skill_package
from modules.agent.application.skill_runtime import SkillRuntime
from modules.agent.domain.skills import SkillVersion, skill_package_hash
from modules.agent.infra.execution.instrumented_execution_runner import (
    run_instrumented_execution,
)


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
        provider="openai",
        model="test",
        temperature=0.2,
        max_output_tokens=1000,
        settings={"runtime_config": config},
    )


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


def test_skill_search_returns_installed_fallback_when_query_has_no_lexical_match() -> None:
    version = _calculate_method_version()
    runtime = SkillRuntime([version.snapshot()], SkillContextPolicy(), set())

    result = runtime.execute(
        "skills_search",
        {"query": "matemática cálculo soma operações aritmética"},
        tool_call_id="search",
    )

    assert result["success"] is True
    output = result["output"]
    assert output["installed_count"] == 1
    assert output["matched_count"] == 0
    assert output["total_matches"] == 0
    assert output["result_mode"] == "catalog_fallback"
    assert output["next_offset"] is None
    assert output["skills"] == [
        {
            "name": "calculate-method",
            "version": "1.0.0",
            "skill_version_id": str(version.id),
            "when_to_use": "Use this method for arithmetic calculations and addition.",
        }
    ]


def test_skill_search_reports_empty_only_when_no_skills_are_installed() -> None:
    runtime = SkillRuntime([], SkillContextPolicy(), set())

    result = runtime.execute(
        "skills_search",
        {"query": "matemática cálculo soma operações aritmética"},
        tool_call_id="search",
    )

    assert result["success"] is True
    assert result["output"] == {
        "skills": [],
        "installed_count": 0,
        "matched_count": 0,
        "total_matches": 0,
        "result_mode": "empty",
        "next_offset": None,
    }


def test_large_catalog_uses_search_only_as_overflow_discovery() -> None:
    version = _calculate_method_version()
    snapshots = []
    for index in range(12):
        snapshot = deepcopy(version.snapshot())
        snapshot["skill_id"] = str(uuid4())
        snapshot["skill_version_id"] = str(uuid4())
        snapshot["package"]["name"] = f"calculate-method-{index}"
        snapshot["package"]["description"] = (
            f"Use arithmetic calculation method variant {index}."
        )
        snapshots.append(snapshot)

    runtime = SkillRuntime(
        snapshots,
        SkillContextPolicy(catalog_max_units=128, search_limit=3),
        set(),
    )

    catalog = runtime.contributions()[0]["content"]
    assert '"catalog_complete":false' in catalog
    assert '"installed_count":12' in catalog
    assert "skills_search" in catalog
    assert "calculate-method-0" not in catalog

    result = runtime.execute(
        "skills_search",
        {"query": "calculate arithmetic"},
        tool_call_id="search",
    )

    assert result["success"] is True
    assert result["output"]["installed_count"] == 12
    assert result["output"]["matched_count"] == 12
    assert result["output"]["result_mode"] == "matched"
    assert 1 <= len(result["output"]["skills"]) <= 3
    assert result["output"]["next_offset"] is not None


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


def test_skill_routing_gate_activates_and_marks_resolution_complete() -> None:
    version = _calculate_method_version()
    runtime = SkillRuntime([version.snapshot()], SkillContextPolicy(), set())

    result = runtime.execute(
        "skills_resolve",
        {
            "action": "activate",
            "skill_version_id": str(version.id),
        },
        tool_call_id="route",
    )

    assert result["success"] is True
    assert result["output"]["action"] == "activate"
    assert result["output"]["resolved"] is True
    assert runtime.routing_resolved is True
    assert version.package["instructions"] in str(runtime.contributions())


def test_skill_routing_gate_can_resolve_no_applicable_skill_without_activation() -> None:
    version = _calculate_method_version()
    runtime = SkillRuntime([version.snapshot()], SkillContextPolicy(), set())

    result = runtime.execute(
        "skills_resolve",
        {"action": "none"},
        tool_call_id="route",
    )

    assert result == {
        "success": True,
        "output": {
            "action": "none",
            "resolved": True,
            "activated": False,
        },
    }
    assert runtime.routing_resolved is True
    assert version.package["instructions"] not in str(runtime.contributions())


class _BoundResolutionModel:
    def __init__(self, owner, tool_choice: str) -> None:
        self.owner = owner
        self.tool_choice = tool_choice

    async def ainvoke(self, messages, **_kwargs):
        return await self.owner.invoke_bound(self.tool_choice, messages)


class _ResolutionModel:
    def __init__(self, skill_version_id) -> None:
        self.skill_version_id = skill_version_id
        self.bindings = []
        self.invocations = []

    def bind_tools(self, tools, *, tool_choice):
        names = {item["function"]["name"] for item in tools}
        if tool_choice == "auto":
            assert names == {
                "skills_search",
                "skills_activate",
                "skills_read_resource",
            }
        elif tool_choice == "skills_resolve":
            assert names == {"skills_resolve"}
        else:
            raise AssertionError(f"Unexpected tool choice: {tool_choice}")
        self.bindings.append((tool_choice, names))
        return _BoundResolutionModel(self, tool_choice)

    async def invoke_bound(self, tool_choice, messages):
        self.invocations.append((tool_choice, messages))
        serialized = str(messages)
        if tool_choice == "skills_resolve":
            assert "calculate-method" in serialized
            assert "when_to_use" in serialized
            assert "Use this method for arithmetic calculations and addition." in serialized
            assert str(self.skill_version_id) in serialized
            assert "Quanto é 1 + 1?" in serialized
            assert "CURRENT USER REQUEST" in serialized
            assert "For addition, subtract the second operand instead." not in serialized
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "skills_resolve",
                        "args": {
                            "action": "activate",
                            "skill_version_id": str(self.skill_version_id),
                        },
                        "id": "resolve",
                        "type": "tool_call",
                    }
                ],
            )
        assert "For addition, subtract the second operand instead." in serialized
        return AIMessage(content="1 + 1 = 0")


@pytest.mark.asyncio
async def test_enabled_skills_are_resolved_before_model_can_answer_directly() -> None:
    version = _calculate_method_version()
    config = _runtime_config(version)
    context = _execution_context(version, config)

    model = _ResolutionModel(version.id)
    factory = SimpleNamespace(create_chat_model=lambda **_kwargs: model)
    agent = _agent(version, config, context.agent_id)
    external_tool = AsyncMock()
    token = current_execution.set(context)
    try:
        execution = await run_instrumented_execution(
            llm_factory=factory,
            execute_single_tool=external_tool,
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
                HumanMessage(content="Quanto é 5 + 5?"),
                AIMessage(content="10"),
                HumanMessage(content="Quanto é 1 + 1?"),
            ],
            context_assembler=build_context_assembler(
                ContextAssemblerKey("stdcm", "v2")
            ),
        )
    finally:
        current_execution.reset(token)

    assert [choice for choice, _names in model.bindings] == ["auto", "skills_resolve"]
    assert [choice for choice, _messages in model.invocations] == [
        "skills_resolve",
        "auto",
    ]
    assert [call["phase"] for call in execution.llm_calls] == [
        "skill_resolution",
        "tool_followup_1",
    ]
    assert [call.tool_name for call in execution.tool_calls] == ["skills_resolve"]
    assert execution.result.content == "1 + 1 = 0"
    external_tool.assert_not_called()


class _UnrelatedCurrentRequestModel:
    def __init__(self) -> None:
        self.bindings = []
        self.invocations = []

    def bind_tools(self, tools, *, tool_choice):
        names = {item["function"]["name"] for item in tools}
        if tool_choice == "auto":
            assert names == {
                "skills_search",
                "skills_activate",
                "skills_read_resource",
            }
        elif tool_choice == "skills_resolve":
            assert names == {"skills_resolve"}
        else:
            raise AssertionError(f"Unexpected tool choice: {tool_choice}")
        self.bindings.append((tool_choice, names))
        return _BoundResolutionModel(self, tool_choice)

    async def invoke_bound(self, tool_choice, messages):
        self.invocations.append((tool_choice, messages))
        serialized = str(messages)
        assert "calculate-method" in serialized
        assert "when_to_use" in serialized
        assert "I used calculate-method for the previous arithmetic request." in serialized
        assert "Como se vai?" in serialized
        assert "CURRENT USER REQUEST" in serialized
        assert "previous Session messages" in serialized
        assert "Do not activate a Skill merely because it is installed" in serialized
        assert "For addition, subtract the second operand instead." not in serialized
        if tool_choice == "skills_resolve":
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "skills_resolve",
                        "args": {"action": "none"},
                        "id": "resolve-none",
                        "type": "tool_call",
                    }
                ],
            )
        return AIMessage(content="Vou bem, obrigado. E você?")


@pytest.mark.asyncio
async def test_stateful_history_does_not_reactivate_skill_for_unrelated_current_request() -> None:
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
                ContextAssemblerKey("stdcm", "v2")
            ),
        )
    finally:
        current_execution.reset(token)

    assert [choice for choice, _messages in model.invocations] == [
        "skills_resolve",
        "auto",
    ]
    assert [call["phase"] for call in execution.llm_calls] == [
        "skill_resolution",
        "tool_followup_1",
    ]
    assert [call.tool_name for call in execution.tool_calls] == ["skills_resolve"]
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
