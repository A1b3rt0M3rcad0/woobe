from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from modules.agent.infra.context_management.managers.resolver import build_runtime_context_assembler
from modules.agent.application.context_assembly import assemble_context
from modules.agent.application.context_policy import ContextPolicyV1
from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.domain.entities import Agent
from modules.agent.domain.enums import Provider, SessionMode
from modules.agent.domain.external_context_contract import compose_external_context_contracts
from modules.agent.infra.execution.frozen_snapshot_runtime import (
    FrozenSnapshotStructuredOutputRuntime,
)
from modules.agent.infra.execution.instrumented_execution_runner import run_instrumented_execution
from modules.agent.infra.execution.release_runtime_resolver import ReleaseRuntimeResolver
from modules.network.domain.external_context_contract import (
    project_effective_external_context,
    resolve_effective_external_context,
)


LEGACY_CONTEXT_POLICY = ContextPolicyV1.model_validate(
    {
        # Existing frozen Agent snapshots can legitimately have this policy shape.
        # External Context exposure must not silently depend on generic RUNTIME being
        # present here because model.expose is already an explicit contract decision.
        "allowed_sources": [
            "SYSTEM",
            "USER_INPUT",
            "SESSION",
            "TOOL",
            "SKILL",
        ]
    }
)


def _contract() -> dict:
    return {
        "age": {
            "schema": {"type": "integer"},
            "required": True,
            "model": {"expose": False},
            "description": "Age supplied by the host application.",
        },
        "name": {
            "schema": {"type": "string"},
            "required": True,
            "model": {"expose": True},
            "description": "Name the Agent should use when addressing the user.",
        },
    }


def _runtime_context(**overrides):
    values = {
        "model_capacity_units": None,
        "reserved_output_units": None,
        "active_tool_definitions": [],
        "context_selection_metadata": {},
        "rag_metadata": {},
        "context_rag_sources": [],
        "parent_invocation_id": None,
        "network_execution_id": uuid4(),
        "network_invocation_id": uuid4(),
        "network_node_id": uuid4(),
        "input_message_id": uuid4(),
        "run_id": uuid4(),
        "external_context_contract": _contract(),
        "external_context_snapshot": {"age": 18, "name": "Alberto"},
        "model_external_context": {"name": "Alberto"},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _assemble(runtime_context, *, policy=LEGACY_CONTEXT_POLICY):
    return assemble_context(
        messages=[
            SystemMessage(content="You are a support Agent."),
            HumanMessage(content="Qual é meu nome?"),
        ],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="custom",
        model="test-model",
        runtime_context=runtime_context,
        policy=policy,
    )


def _materialized_text(result) -> str:
    return "\n".join(str(message.content) for message in result.messages)


def test_exposed_external_context_reaches_model_even_when_legacy_policy_omits_runtime() -> None:
    result = _assemble(_runtime_context())
    materialized = _materialized_text(result)

    assert "External Context supplied by the runtime" in materialized
    assert '"name"' in materialized
    assert '"Alberto"' in materialized
    assert '"age"' not in materialized

    contribution = next(
        item
        for item in result.snapshot.contributions
        if item.source_ref == "external_context"
    )
    assert contribution.selection_method == "runtime_external_context"


def test_external_context_description_reaches_model_with_the_exposed_value() -> None:
    result = _assemble(_runtime_context())
    materialized = _materialized_text(result)

    assert "Name the Agent should use when addressing the user." in materialized
    assert "Age supplied by the host application." not in materialized


def test_contract_exposure_does_not_enable_unrelated_runtime_context() -> None:
    unrelated_runtime = SystemMessage(
        content="UNRELATED_RUNTIME_MESSAGE_SHOULD_NOT_REACH_MODEL",
        additional_kwargs={
            "woobe_context": {
                "source_type": "RUNTIME",
                "source_ref": "runtime_test_fixture",
                "selection_method": "runtime_test",
            }
        },
    )
    result = assemble_context(
        messages=[
            SystemMessage(content="You are a support Agent."),
            unrelated_runtime,
            HumanMessage(content="Qual é meu nome?"),
        ],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="custom",
        model="test-model",
        runtime_context=_runtime_context(),
        policy=LEGACY_CONTEXT_POLICY,
    )
    materialized = _materialized_text(result)

    assert '"Alberto"' in materialized
    assert "UNRELATED_RUNTIME_MESSAGE_SHOULD_NOT_REACH_MODEL" not in materialized


def test_network_projection_resolver_and_context_manager_materialize_exposed_field() -> None:
    node_id = str(uuid4())
    contract = _contract()
    effective = compose_external_context_contracts({node_id: contract})
    accepted = resolve_effective_external_context(
        effective,
        {"age": 18, "name": "Alberto"},
    )
    projected = project_effective_external_context(
        effective,
        node_id,
        accepted.snapshot,
    )

    assert projected == {"age": 18, "name": "Alberto"}

    runtime_context = new_execution_context()
    runtime_context.project_id = uuid4()
    runtime_context.agent_id = uuid4()
    runtime_context.network_execution_id = uuid4()
    runtime_context.network_invocation_id = uuid4()
    runtime_context.network_node_id = uuid4()
    runtime_context.model_capacity_units = None
    runtime_context.reserved_output_units = None
    runtime_context.active_tool_definitions = []
    runtime_context.context_selection_metadata = {}
    runtime_context.rag_metadata = {}
    runtime_context.context_rag_sources = []
    runtime_context.input_message_id = uuid4()

    request = AskInput(
        project_id=runtime_context.project_id,
        agent_id=runtime_context.agent_id,
        message="Qual é meu nome?",
        external_context=projected,
        execution_context="playground",
        metadata={"source": "network_runtime", "defer_persistence": True},
    )
    agent = SimpleNamespace(settings={"external_context_contract": contract})
    resolver = ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)

    token = current_execution.set(runtime_context)
    try:
        resolver._resolve_external_context(
            agent=agent,
            input_dto=request,
        )

        assert runtime_context.external_context_snapshot == {
            "age": 18,
            "name": "Alberto",
        }
        assert runtime_context.model_external_context == {"name": "Alberto"}

        result = _assemble(runtime_context)
        materialized = _materialized_text(result)

        assert '"Alberto"' in materialized
        assert '"age"' not in materialized
        assert any(
            contribution.source_ref == "external_context"
            for contribution in result.snapshot.contributions
        )
    finally:
        current_execution.reset(token)


class _CapturingModel:
    def __init__(self) -> None:
        self.received: list = []

    async def ainvoke(self, messages, **_kwargs):
        self.received = list(messages)
        return AIMessage(content="Alberto")


class _CapturingFactory:
    def __init__(self, model: _CapturingModel) -> None:
        self.model = model

    def create_chat_model(self, **_kwargs):
        return self.model


async def _unused_tool(*_args, **_kwargs):
    raise AssertionError("No Tool should execute in this regression test")


def _runtime_agent_config() -> dict:
    return {
        "context": {
            "allowed_sources": [
                "SYSTEM",
                "USER_INPUT",
                "SESSION",
                "TOOL",
                "SKILL",
            ]
        }
    }


def _materialized_model_text(messages: list) -> str:
    return "\n".join(str(message.content) for message in messages)


@pytest.mark.asyncio
async def test_actual_model_invocation_receives_contract_exposed_external_context() -> None:
    context = new_execution_context()
    context.project_id = uuid4()
    context.agent_id = uuid4()
    context.run_id = uuid4()
    context.network_execution_id = uuid4()
    context.network_invocation_id = uuid4()
    context.network_node_id = uuid4()
    context.external_context_contract = _contract()
    context.external_context_snapshot = {"age": 18, "name": "Alberto"}
    context.model_external_context = {"name": "Alberto"}

    model = _CapturingModel()
    factory = _CapturingFactory(model)
    agent = SimpleNamespace(
        project_id=context.project_id,
        provider="custom",
        model="test-model",
        temperature=0.2,
        max_output_tokens=1000,
        settings={"runtime_config": _runtime_agent_config()},
    )

    token = current_execution.set(context)
    try:
        await run_instrumented_execution(
            llm_factory=factory,
            execute_single_tool=_unused_tool,
            clean_json_answer=lambda value: value,
            agent=agent,
            api_key="fixture",
            base_url=None,
            response_format={},
            json_enabled=False,
            has_tools=False,
            agent_tools=[],
            tool_name_to_id={},
            messages=[
                SystemMessage(content="You are a support Agent."),
                HumanMessage(content="Qual é meu nome?"),
            ],
            context_assembler=build_runtime_context_assembler(),
        )
    finally:
        current_execution.reset(token)

    materialized = _materialized_model_text(model.received)
    assert "External Context supplied by the runtime" in materialized
    assert '"name"' in materialized
    assert '"Alberto"' in materialized
    assert '"age"' not in materialized


def _external_context_messages(result) -> list:
    return [
        message
        for message in result.messages
        if (
            isinstance(getattr(message, "additional_kwargs", None), dict)
            and (
                message.additional_kwargs.get("woobe_context", {}).get("source_ref")
                == "external_context"
            )
        )
    ]


def test_structured_external_context_reaches_model_without_losing_json_types() -> None:
    contract = {
        "profile": {
            "schema": {
                "type": "object",
                "properties": {
                    "active": {"type": "boolean"},
                    "age": {"type": "integer"},
                    "roles": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["active", "age", "roles"],
                "additionalProperties": False,
            },
            "required": True,
            "model": {"expose": True},
            "description": "Authenticated user profile.",
        },
        "secret": {
            "schema": {"type": "string"},
            "required": True,
            "model": {"expose": False},
        },
    }
    runtime = _runtime_context(
        external_context_contract=contract,
        external_context_snapshot={
            "profile": {
                "active": True,
                "age": 18,
                "roles": ["admin", "billing"],
            },
            "secret": "must-not-reach-model",
        },
        model_external_context={
            "profile": {
                "active": True,
                "age": 18,
                "roles": ["admin", "billing"],
            }
        },
    )

    result = _assemble(runtime)
    messages = _external_context_messages(result)

    assert len(messages) == 1
    payload = json.loads(str(messages[0].content).split("\n", 1)[1])
    assert payload == {
        "profile": {
            "description": "Authenticated user profile.",
            "value": {
                "active": True,
                "age": 18,
                "roles": ["admin", "billing"],
            },
        }
    }
    assert "must-not-reach-model" not in _materialized_text(result)


def test_repeated_model_invocations_on_same_run_materialize_one_identical_context_message_each() -> None:
    runtime = _runtime_context()

    first = _assemble(runtime)
    second = _assemble(runtime)

    first_messages = _external_context_messages(first)
    second_messages = _external_context_messages(second)

    assert len(first_messages) == 1
    assert len(second_messages) == 1
    assert first_messages[0].content == second_messages[0].content
    assert _materialized_text(first).count("External Context supplied by the runtime") == 1
    assert _materialized_text(second).count("External Context supplied by the runtime") == 1


def test_external_context_remains_structurally_valid_under_context_budget_pressure() -> None:
    large_value = "x" * 2_000
    contract = {
        "profile": {
            "schema": {"type": "string"},
            "required": True,
            "model": {"expose": True},
            "description": "Large runtime profile.",
        }
    }
    runtime = _runtime_context(
        external_context_contract=contract,
        external_context_snapshot={"profile": large_value},
        model_external_context={"profile": large_value},
        model_capacity_units=512,
        reserved_output_units=128,
    )
    policy = ContextPolicyV1.model_validate(
        {
            "allowed_sources": [
                "SYSTEM",
                "USER_INPUT",
                "SESSION",
                "TOOL",
                "SKILL",
            ],
            "budget": {
                "max_input_units": 256,
                "runtime_reserve_units": 0,
            },
        }
    )

    result = _assemble(runtime, policy=policy)
    messages = _external_context_messages(result)

    assert len(messages) == 1
    serialized_payload = str(messages[0].content).split("\n", 1)[1]
    parsed = json.loads(serialized_payload)
    assert "profile" in parsed
    assert isinstance(parsed["profile"], dict)


@pytest.mark.asyncio
async def test_network_frozen_snapshot_external_context_reaches_actual_model_and_evidence() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    frozen_contract = _contract()
    live_agent = Agent(
        id=agent_id,
        project_id=project_id,
        provider=Provider.custom,
        model="live-model",
        session_mode=SessionMode.stateful,
        settings={
            "external_context_contract": {
                "legacy_name": {
                    "schema": {"type": "string"},
                    "required": False,
                            "model": {"expose": False},
                }
            },
            "runtime_config": {},
        },
    )
    frozen_snapshot = {
        "provider": "custom",
        "model": "test-model",
        "session_mode": "stateful",
        "external_context_contract": frozen_contract,
        "runtime_config": _runtime_agent_config(),
    }

    runtime = FrozenSnapshotStructuredOutputRuntime.__new__(
        FrozenSnapshotStructuredOutputRuntime
    )
    runtime._apply_snapshot_override(live_agent, frozen_snapshot)

    context = new_execution_context()
    context.project_id = project_id
    context.agent_id = agent_id
    context.run_id = uuid4()
    context.network_execution_id = uuid4()
    context.network_invocation_id = uuid4()
    context.network_node_id = uuid4()
    context.model_capacity_units = None
    context.reserved_output_units = None
    context.active_tool_definitions = []
    context.context_selection_metadata = {}
    context.rag_metadata = {}
    context.context_rag_sources = []
    context.input_message_id = uuid4()

    request = AskInput(
        project_id=project_id,
        agent_id=agent_id,
        message="Qual é meu nome?",
        external_context={"age": 18, "name": "Alberto"},
        execution_context="playground",
        metadata={"source": "network_runtime", "defer_persistence": True},
    )
    resolver = ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)
    model = _CapturingModel()

    token = current_execution.set(context)
    try:
        resolver._resolve_external_context(
            agent=live_agent,
            input_dto=request,
        )

        execution = await run_instrumented_execution(
            llm_factory=_CapturingFactory(model),
            execute_single_tool=_unused_tool,
            clean_json_answer=lambda value: value,
            agent=live_agent,
            api_key="fixture",
            base_url=None,
            response_format={},
            json_enabled=False,
            has_tools=False,
            agent_tools=[],
            tool_name_to_id={},
            messages=[
                SystemMessage(content="You are a support Agent."),
                HumanMessage(content=request.message),
            ],
            context_assembler=build_runtime_context_assembler(),
        )
    finally:
        current_execution.reset(token)

    assert live_agent.settings["external_context_contract"] == frozen_contract
    assert context.external_context_snapshot == {"age": 18, "name": "Alberto"}
    assert context.model_external_context == {"name": "Alberto"}

    materialized = _materialized_model_text(model.received)
    assert "External Context supplied by the runtime" in materialized
    assert '"name"' in materialized
    assert '"Alberto"' in materialized
    assert '"age"' not in materialized

    snapshot = execution.llm_calls[-1]["context_snapshot"]
    external_context_contributions = [
        contribution
        for contribution in snapshot["contributions"]
        if contribution["source_ref"] == "external_context"
    ]
    assert len(external_context_contributions) == 1
    assert (
        external_context_contributions[0]["selection_method"]
        == "runtime_external_context"
    )
