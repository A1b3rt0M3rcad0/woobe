from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from modules.agent.application.interfaces.context_assembler import (
    ContextAssemblyRequest,
    ContextSummaryModelResult,
)
from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.domain.context import ContextSourceType
from modules.agent.infra.context_management.managers.resolver import (
    build_context_assembler,
)


class _Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict, bool]] = []

    async def emit(self, event_type, payload, *, durable=False):
        self.events.append((event_type, payload, durable))
        return None


def _runtime(*, recorder=None, state=None):
    return SimpleNamespace(
        run_id=uuid4(),
        input_message_id=uuid4(),
        model_capacity_units=2_000,
        reserved_output_units=200,
        active_tool_definitions=None,
        context_selection_metadata=None,
        rag_metadata=None,
        context_rag_sources=None,
        parent_invocation_id=None,
        network_execution_id=None,
        network_invocation_id=None,
        network_node_id=None,
        skill_context=None,
        external_context_contract=None,
        model_external_context=None,
        context_manager_state=state,
        run_event_recorder=recorder,
    )


def _messages() -> list:
    return [
        SystemMessage(content="System"),
        HumanMessage(content="old user one " * 80),
        AIMessage(content="old answer one " * 80),
        HumanMessage(content="old user two " * 80),
        AIMessage(content="old answer two " * 80),
        HumanMessage(content="current user"),
    ]


def _policy(*, strategy: str = "pressure_triggered") -> ContextPolicyV1:
    return ContextPolicyV1.model_validate(
        {
            "budget": {"max_input_units": 1_500},
            "summary": {
                "strategy": strategy,
                "sources": ["SESSION"],
                "trigger_at": 0.20,
                "target_units": 128,
                "preserve_recent_messages": 1,
                "refresh_after_messages": 2,
                "failure_mode": "fallback_to_selection",
            },
        }
    )


@pytest.mark.asyncio
async def test_standard_never_invokes_semantic_summary_even_when_policy_enables_it() -> None:
    calls = 0

    async def summary_invoke(_messages, _phase):
        nonlocal calls
        calls += 1
        return ContextSummaryModelResult(content="should not run")

    request = ContextAssemblyRequest(
        messages=_messages(),
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test",
        runtime_context=_runtime(),
        policy=_policy(),
        summary_invoke=summary_invoke,
    )

    output = await build_context_assembler("standard").assemble(request)

    assert calls == 0
    assert not any(
        "semantic_summary" in contribution.transformations
        for contribution in output.snapshot.contributions
    )


@pytest.mark.asyncio
async def test_adaptive_creates_semantic_summary_and_durable_checkpoint_under_pressure() -> None:
    calls = 0
    recorder = _Recorder()
    runtime = _runtime(recorder=recorder)

    async def summary_invoke(_messages, phase):
        nonlocal calls
        calls += 1
        assert phase == "context_summary"
        return ContextSummaryModelResult(
            content="The user discussed two historical items and prior answers.",
            model_invocation_id=uuid4(),
            provider="test",
            model="summary-test",
        )

    request = ContextAssemblyRequest(
        messages=_messages(),
        model_invocation_id=uuid4(),
        agent_run_id=runtime.run_id,
        project_id=uuid4(),
        provider="test",
        model="test",
        runtime_context=runtime,
        policy=_policy(),
        summary_invoke=summary_invoke,
    )

    output = await build_context_assembler("adaptive").assemble(request)

    assert calls == 1
    assert runtime.context_manager_state["manager_name"] == "adaptive"
    assert runtime.context_manager_state["boundary"] == "context_summary_boundary"
    assert runtime.context_manager_state["state"]["summary_generation"] == 1
    assert recorder.events
    assert recorder.events[-1][0] == "context.checkpoint"
    assert recorder.events[-1][2] is True

    summaries = [
        item
        for item in output.snapshot.contributions
        if "semantic_summary" in item.transformations
    ]
    assert len(summaries) == 1
    assert summaries[0].source_type == ContextSourceType.SESSION
    assert summaries[0].raw_units > summaries[0].materialized_units
    assert output.messages[-1].content == "current user"


@pytest.mark.asyncio
async def test_adaptive_reuses_checkpointed_summary_without_second_model_call() -> None:
    calls = 0
    runtime = _runtime()

    async def summary_invoke(_messages, _phase):
        nonlocal calls
        calls += 1
        return ContextSummaryModelResult(
            content="Reusable historical summary.",
            model_invocation_id=uuid4(),
            provider="test",
            model="summary-test",
        )

    manager = build_context_assembler("adaptive")
    first = ContextAssemblyRequest(
        messages=_messages(),
        model_invocation_id=uuid4(),
        agent_run_id=runtime.run_id,
        project_id=uuid4(),
        provider="test",
        model="test",
        runtime_context=runtime,
        policy=_policy(),
        summary_invoke=summary_invoke,
    )
    await manager.assemble(first)

    second = ContextAssemblyRequest(
        messages=_messages(),
        model_invocation_id=uuid4(),
        agent_run_id=runtime.run_id,
        project_id=first.project_id,
        provider="test",
        model="test",
        runtime_context=runtime,
        policy=_policy(),
        summary_invoke=summary_invoke,
    )
    output = await manager.assemble(second)

    assert calls == 1
    assert runtime.context_manager_state["state"]["summary_generation"] == 1
    assert any(
        "semantic_summary" in item.transformations
        for item in output.snapshot.contributions
    )


@pytest.mark.asyncio
async def test_adaptive_falls_back_to_deterministic_selection_when_summary_fails() -> None:
    async def summary_invoke(_messages, _phase):
        raise RuntimeError("summary provider unavailable")

    request = ContextAssemblyRequest(
        messages=_messages(),
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test",
        runtime_context=_runtime(),
        policy=_policy(),
        summary_invoke=summary_invoke,
    )

    output = await build_context_assembler("adaptive").assemble(request)

    assert output.messages[-1].content == "current user"
    assert not any(
        "semantic_summary" in item.transformations
        for item in output.snapshot.contributions
    )
