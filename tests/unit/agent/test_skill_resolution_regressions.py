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
            "description": "Use this method for arithmetic calculations and addition.",
            "version": "1.0.0",
            "skill_version_id": str(version.id),
            "required_tools": [],
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
    assert "12 installed Skills. Use skills_search" in catalog
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


class _ResolutionModel:
    def __init__(self, skill_version_id) -> None:
        self.skill_version_id = skill_version_id
        self.bindings = []
        self.invocations = []

    def bind_tools(self, tools, *, tool_choice):
        names = {item["function"]["name"] for item in tools}
        assert names == {
            "skills_search",
            "skills_activate",
            "skills_read_resource",
        }
        assert tool_choice == "auto"
        self.bindings.append(tool_choice)
        return self

    async def ainvoke(self, messages, **_kwargs):
        self.invocations.append(messages)
        call_index = len(self.invocations)
        if call_index == 1:
            serialized = str(messages)
            assert "calculate-method" in serialized
            assert "Use this method for arithmetic calculations and addition." in serialized
            assert str(self.skill_version_id) in serialized
            assert "Quanto é 1 + 1?" in serialized
            assert not any(
                message.__class__.__name__ == "ToolMessage" for message in messages
            )
            assert not any(
                isinstance(message, AIMessage)
                and any(
                    call.get("name") == "skills_search"
                    for call in (message.tool_calls or [])
                )
                for message in messages
            )
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
        assert "subtract the second operand" in str(messages)
        return AIMessage(content="1 + 1 = 0")


@pytest.mark.asyncio
async def test_enabled_skills_are_known_before_model_and_activate_without_search() -> None:
    version = _calculate_method_version()
    config = _runtime_config(version)
    context = new_execution_context()
    context.project_id = version.project_id
    context.agent_id = uuid4()
    context.run_id = uuid4()
    context.context_policy = resolve_context_policy(config).model_dump(mode="json")

    model = _ResolutionModel(version.id)
    factory = SimpleNamespace(create_chat_model=lambda **_kwargs: model)
    agent = SimpleNamespace(
        id=context.agent_id,
        project_id=version.project_id,
        provider="openai",
        model="test",
        temperature=0.2,
        max_output_tokens=1000,
        settings={"runtime_config": config},
    )
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

    assert model.bindings == ["auto"]
    assert [call["phase"] for call in execution.llm_calls] == [
        "capability_response_generation",
        "tool_followup_1",
    ]
    assert [call.tool_name for call in execution.tool_calls] == ["skills_activate"]
    assert execution.result.content == "1 + 1 = 0"
    external_tool.assert_not_called()


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
