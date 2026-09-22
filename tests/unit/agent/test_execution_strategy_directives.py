from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from modules.agent.application.context_assembly import assemble_context
from modules.agent.application.context_policy import ContextPolicyV1
from modules.agent.domain.context import ContextPriority, ContextSourceType
from modules.agent.infra.execution.capabilities.model_invocation import (
    ModelInvocationCapability,
)
from modules.agent.infra.execution.strategy_runtime.model import (
    RuntimeStrategyModel,
    _messages_with_execution_directive,
)
from modules.agent.infra.execution.strategy_runtime.runtime_state import StrategyRuntimeState


def _directive_messages(messages: list[Any]) -> list[Any]:
    directives = []
    for message in messages:
        metadata = getattr(message, "additional_kwargs", {}).get("woobe_context", {})
        if metadata.get("kind") == "execution_directive":
            directives.append(message)
    return directives


def _runtime_model(
    *,
    base_messages: list[Any],
    runtime_state: StrategyRuntimeState,
    invoke_fn,
    communication_model: Any | None = None,
    communication_model_factory=None,
    final_model: Any | None = None,
) -> RuntimeStrategyModel:
    return RuntimeStrategyModel(
        capability=ModelInvocationCapability(
            model=object(),
            provider="test",
            model_name="test-model",
            invoke_fn=invoke_fn,
        ),
        runtime_state=runtime_state,
        base_messages=base_messages,
        initial_phase="response_generation",
        communication_model=communication_model,
        communication_model_factory=communication_model_factory,
        final_model=final_model,
        final_model_factory=None,
        final_json_instruction=None,
    )


@pytest.mark.asyncio
async def test_runtime_strategy_model_directive_is_invocation_local() -> None:
    captured_messages: list[list[Any]] = []

    async def fake_invoke_llm(**kwargs):
        captured_messages.append(list(kwargs["messages"]))
        call_index = kwargs["call_index"]
        return (
            AIMessage(content=f"result-{call_index}"),
            {
                "phase": kwargs["phase"],
                "call_index": call_index,
                "occurred_at": f"model-{call_index}",
            },
        )

    base_messages = [
        SystemMessage(content="Agent behavior"),
        HumanMessage(content="Analyze the evidence."),
    ]
    runtime_state = StrategyRuntimeState(
        messages=list(base_messages),
        base_message_count=len(base_messages),
    )
    model = _runtime_model(
        base_messages=base_messages,
        runtime_state=runtime_state,
        invoke_fn=fake_invoke_llm,
    )

    await model.invoke(
        phase="reflect",
        directive="Evaluate the evidence and identify unresolved gaps.",
    )

    assert len(_directive_messages(captured_messages[0])) == 1
    directive = _directive_messages(captured_messages[0])[0]
    metadata = directive.additional_kwargs["woobe_context"]
    assert metadata["source_type"] == "SYSTEM"
    assert metadata["kind"] == "execution_directive"
    assert metadata["phase"] == "reflect"
    assert metadata["selection_method"] == "strategy_directive"
    assert "Evaluate the evidence" in directive.content
    assert _directive_messages(runtime_state.messages) == []

    await model.invoke(phase="continue")

    assert len(captured_messages) == 2
    assert _directive_messages(captured_messages[1]) == []
    assert _directive_messages(runtime_state.messages) == []


@pytest.mark.asyncio
async def test_communicate_uses_tool_free_model_and_intermediate_output_mode() -> None:
    captured: list[dict[str, Any]] = []
    communication_model = object()

    async def fake_invoke_llm(**kwargs):
        captured.append(dict(kwargs))
        return (
            AIMessage(content="Vou procurar e volto com o que encontrar."),
            {
                "phase": kwargs["phase"],
                "call_index": kwargs["call_index"],
                "occurred_at": "model-1",
            },
        )

    base_messages = [HumanMessage(content="Pesquise isso.")]
    runtime_state = StrategyRuntimeState(
        messages=list(base_messages),
        base_message_count=len(base_messages),
    )
    model = _runtime_model(
        base_messages=base_messages,
        runtime_state=runtime_state,
        invoke_fn=fake_invoke_llm,
        communication_model=communication_model,
    )

    result = await model.communicate(
        phase="search_update",
        directive="Briefly tell the user what you will verify next.",
    )

    assert result.content == "Vou procurar e volto com o que encontrar."
    assert len(captured) == 1
    assert captured[0]["model"] is communication_model
    assert captured[0]["output_mode"] == "intermediate"
    assert captured[0]["phase"] == "search_update"
    assert runtime_state.messages[-1].content == (
        "Vou procurar e volto com o que encontrar."
    )




@pytest.mark.asyncio
async def test_communicate_resolves_lazy_model_once() -> None:
    captured: list[dict[str, Any]] = []
    created: list[object] = []
    lazy_model = object()

    async def fake_invoke_llm(**kwargs):
        captured.append(dict(kwargs))
        return (
            AIMessage(content="Progress update."),
            {
                "phase": kwargs["phase"],
                "call_index": kwargs["call_index"],
                "occurred_at": f"model-{kwargs['call_index']}",
            },
        )

    def communication_factory():
        created.append(lazy_model)
        return lazy_model

    base_messages = [HumanMessage(content="Investigate.")]
    runtime_state = StrategyRuntimeState(
        messages=list(base_messages),
        base_message_count=len(base_messages),
    )
    model = _runtime_model(
        base_messages=base_messages,
        runtime_state=runtime_state,
        invoke_fn=fake_invoke_llm,
        communication_model_factory=communication_factory,
    )

    await model.communicate(phase="update_1")
    await model.communicate(phase="update_2")

    assert created == [lazy_model]
    assert [item["model"] for item in captured] == [lazy_model, lazy_model]
    assert [item["output_mode"] for item in captured] == [
        "intermediate",
        "intermediate",
    ]


@pytest.mark.asyncio
async def test_finalize_directive_is_invocation_local() -> None:
    captured_messages: list[list[Any]] = []

    async def fake_invoke_llm(**kwargs):
        captured_messages.append(list(kwargs["messages"]))
        call_index = kwargs["call_index"]
        return (
            AIMessage(content="final-result"),
            {
                "phase": kwargs["phase"],
                "call_index": call_index,
                "occurred_at": f"model-{call_index}",
            },
        )

    base_messages = [
        SystemMessage(content="Agent behavior"),
        HumanMessage(content="Analyze the evidence."),
    ]
    runtime_state = StrategyRuntimeState(
        messages=list(base_messages),
        base_message_count=len(base_messages),
    )
    model = _runtime_model(
        base_messages=base_messages,
        runtime_state=runtime_state,
        invoke_fn=fake_invoke_llm,
        final_model=object(),
    )

    await model.finalize(
        reason="capability round limit reached",
        phase="final_response_generation",
        directive="Synthesize the validated evidence into the final answer.",
    )

    directives = _directive_messages(captured_messages[0])
    assert len(directives) == 1
    assert (
        directives[0].additional_kwargs["woobe_context"]["phase"]
        == "final_response_generation"
    )
    assert "Synthesize the validated evidence" in directives[0].content
    assert _directive_messages(runtime_state.messages) == []


def test_execution_directive_is_accounted_as_mandatory_system_context() -> None:
    base_messages = [
        SystemMessage(content="Agent behavior"),
        HumanMessage(content="Analyze the evidence."),
    ]
    messages = _messages_with_execution_directive(
        base_messages,
        phase="reflect",
        directive="Evaluate the evidence and identify unresolved gaps.",
    )
    runtime_context = SimpleNamespace(
        parent_invocation_id=None,
        model_capacity_units=None,
        reserved_output_units=None,
        active_tool_definitions=None,
        input_message_id=uuid4(),
        run_id=uuid4(),
        context_selection_metadata=None,
        rag_metadata=None,
        context_rag_sources=None,
    )
    project_id = uuid4()
    run_id = uuid4()
    policy = ContextPolicyV1()

    baseline = assemble_context(
        messages=base_messages,
        model_invocation_id=uuid4(),
        agent_run_id=run_id,
        project_id=project_id,
        provider="test",
        model="test-model",
        runtime_context=runtime_context,
        policy=policy,
    )
    assembled = assemble_context(
        messages=messages,
        model_invocation_id=uuid4(),
        agent_run_id=run_id,
        project_id=project_id,
        provider="test",
        model="test-model",
        runtime_context=runtime_context,
        policy=policy,
    )

    contribution = next(
        item
        for item in assembled.snapshot.contributions
        if item.metadata.get("kind") == "execution_directive"
    )
    assert contribution.source_type == ContextSourceType.SYSTEM
    assert contribution.priority == ContextPriority.MANDATORY
    assert contribution.source_ref == "execution_directive:reflect"
    assert contribution.selection_method == "strategy_directive"
    assert contribution.trust == "system-controlled"
    assert (
        assembled.snapshot.estimated_input_units
        > baseline.snapshot.estimated_input_units
    )
    assert assembled.snapshot.materialized_hash != baseline.snapshot.materialized_hash


def test_blank_directive_does_not_change_invocation_messages() -> None:
    messages = [
        SystemMessage(content="Agent behavior"),
        HumanMessage(content="Hello"),
    ]

    materialized = _messages_with_execution_directive(
        messages,
        phase="reflect",
        directive="   ",
    )

    assert materialized is messages
    assert _directive_messages(materialized) == []
