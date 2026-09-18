from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from modules.agent.application.context_assembler_registry import build_runtime_context_assembler
from modules.agent.application.context_assembly import assemble_context
from modules.agent.application.context_policy import ContextPolicyV1
from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.domain.external_context_contract import compose_external_context_contracts
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
            "scope": "session",
            "model": {"expose": False},
            "description": "Age supplied by the host application.",
        },
        "name": {
            "schema": {"type": "string"},
            "required": True,
            "scope": "session",
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
            session_data={},
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


import pytest


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
