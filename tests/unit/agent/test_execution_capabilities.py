from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.infra.execution.capabilities.bundle import (
    ExecutionCapabilities,
    build_execution_capabilities,
)
from modules.agent.infra.execution.capabilities.preparation import prepare_execution
from modules.agent.infra.execution.capabilities.state import StrategyExecutionState
from modules.agent.infra.execution.capabilities.tool_execution import ToolExecutionCapability


class _FakeModelFactory:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.model = object()

    def create_chat_model(self, **kwargs):
        self.calls.append(kwargs)
        return self.model


def _request(*, llm_factory=None) -> ExecutionStrategyRequest:
    return ExecutionStrategyRequest(
        llm_factory=llm_factory or _FakeModelFactory(),
        execute_single_tool=lambda *_args: None,  # type: ignore[arg-type]
        clean_json_answer=lambda value: value,
        agent=SimpleNamespace(
            provider="openai",
            model="test-model",
            temperature=0.2,
            max_output_tokens=256,
            settings={},
        ),  # type: ignore[arg-type]
        api_key="secret",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=False,
        agent_tools=[],
        tool_name_to_id={},
        messages=["user-message"],
        context_assembler=None,
    )


@pytest.mark.asyncio
async def test_model_capability_supports_multi_pass_strategy_without_legacy_runner(
    monkeypatch,
) -> None:
    invocations: list[tuple[str, int]] = []

    async def fake_invoke_llm(**kwargs):
        phase = kwargs["phase"]
        call_index = kwargs["call_index"]
        invocations.append((phase, call_index))
        return (
            SimpleNamespace(content=f"result-{call_index}"),
            {
                "phase": phase,
                "call_index": call_index,
                "occurred_at": f"t{call_index}",
            },
        )

    monkeypatch.setattr(
        "modules.agent.infra.execution.capabilities.model_invocation.invoke_llm",
        fake_invoke_llm,
    )

    prepared = prepare_execution(_request())
    capabilities = build_execution_capabilities(
        prepared=prepared,
        strategy_name="test_multi_pass",
    )
    state = StrategyExecutionState(messages=list(prepared.messages))

    for iteration in range(2):
        call_index = iteration + 1
        result, call = await capabilities.model.invoke(
            messages=state.messages,
            phase=f"iterative_pass_{call_index}",
            call_index=call_index,
        )
        state.iteration += 1
        state.record_model_result(result=result, call=call)
        state.messages.append(result)

    execution = state.finish()

    assert isinstance(execution, InstrumentedExecution)
    assert execution.result.content == "result-2"
    assert len(execution.llm_calls) == 2
    assert state.iteration == 2
    assert invocations == [
        ("iterative_pass_1", 1),
        ("iterative_pass_2", 2),
    ]


@pytest.mark.asyncio
async def test_tool_capability_preserves_bound_tool_resolution_and_durable_path(
    monkeypatch,
) -> None:
    captured: list[tuple[str, str]] = []

    async def fake_execute_tool_call(**kwargs):
        tool_call = kwargs["tool_call"]
        resolved_tool_id = kwargs["resolved_tool_id"]
        captured.append((tool_call["name"], resolved_tool_id))
        return (
            SimpleNamespace(duration_ms=3, success=True),
            SimpleNamespace(content="tool-result"),
            {"occurred_at": "tool-time"},
        )

    monkeypatch.setattr(
        "modules.agent.infra.execution.capabilities.tool_execution.execute_tool_call",
        fake_execute_tool_call,
    )
    capability = ToolExecutionCapability(
        execute_single_tool=lambda *_args: None,  # type: ignore[arg-type]
        tool_name_to_id={"search": "tool-id"},
    )

    batch = await capability.execute_many(
        [{"id": "call-1", "name": "search", "args": {"q": "woobe"}}]
    )

    assert captured == [("search", "tool-id")]
    assert len(batch.results) == 1
    assert batch.wall_latency_ms >= 0


def test_execution_state_accumulates_tool_batch_without_owning_tool_execution() -> None:
    from modules.agent.infra.execution.capabilities.tool_execution import ToolExecutionBatch

    state = StrategyExecutionState(messages=[])
    info = SimpleNamespace(duration_ms=5, success=True)
    message = SimpleNamespace(content="tool-result")
    batch = ToolExecutionBatch(
        results=[(info, message, {"occurred_at": "tool-time"})],
        wall_latency_ms=7,
    )

    state.record_tool_batch(batch)

    assert state.execution.tool_calls == [info]
    assert state.execution.tool_wall_latency_ms == 7
    assert state.execution.tool_call_duration_sum_ms == 5
    assert state.messages == [message]
    assert state.execution.timeline == [
        {
            "kind": "tool",
            "occurred_at": "tool-time",
            "payload": {"occurred_at": "tool-time"},
        }
    ]


@pytest.mark.asyncio
async def test_strategy_can_own_model_tool_model_loop_with_shared_capabilities(
    monkeypatch,
) -> None:
    model_calls: list[int] = []
    tool_calls: list[str] = []

    async def fake_invoke_llm(**kwargs):
        call_index = kwargs["call_index"]
        model_calls.append(call_index)
        if call_index == 1:
            result = SimpleNamespace(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "search",
                        "args": {"q": "woobe"},
                    }
                ],
            )
        else:
            result = SimpleNamespace(content="final-answer", tool_calls=[])
        return (
            result,
            {
                "phase": kwargs["phase"],
                "call_index": call_index,
                "occurred_at": f"model-{call_index}",
            },
        )

    async def fake_execute_tool_call(**kwargs):
        tool_call = kwargs["tool_call"]
        tool_calls.append(tool_call["name"])
        return (
            SimpleNamespace(duration_ms=4, success=True),
            SimpleNamespace(content="search-result"),
            {"occurred_at": "tool-1"},
        )

    monkeypatch.setattr(
        "modules.agent.infra.execution.capabilities.model_invocation.invoke_llm",
        fake_invoke_llm,
    )
    monkeypatch.setattr(
        "modules.agent.infra.execution.capabilities.tool_execution.execute_tool_call",
        fake_execute_tool_call,
    )

    request = _request()
    prepared = prepare_execution(request)
    built = build_execution_capabilities(
        prepared=prepared,
        strategy_name="test_model_tool_model",
    )
    capabilities = ExecutionCapabilities(
        model=built.model,
        tools=ToolExecutionCapability(
            execute_single_tool=request.execute_single_tool,
            tool_name_to_id={"search": "tool-id"},
        ),
        knowledge=built.knowledge,
        context=built.context,
        recovery=built.recovery,
    )
    state = StrategyExecutionState(messages=list(prepared.messages))

    first_result, first_call = await capabilities.model.invoke(
        messages=state.messages,
        phase="iterative_reasoning_1",
        call_index=1,
    )
    state.iteration += 1
    state.record_model_result(result=first_result, call=first_call)
    state.messages.append(first_result)

    batch = await capabilities.tools.execute_many(first_result.tool_calls)
    state.record_tool_batch(batch)

    second_result, second_call = await capabilities.model.invoke(
        messages=state.messages,
        phase="iterative_reasoning_2",
        call_index=2,
    )
    state.iteration += 1
    state.record_model_result(result=second_result, call=second_call)

    execution = state.finish()

    assert model_calls == [1, 2]
    assert tool_calls == ["search"]
    assert execution.result.content == "final-answer"
    assert len(execution.llm_calls) == 2
    assert len(execution.tool_calls) == 1
    assert [item["kind"] for item in execution.timeline] == ["llm", "tool", "llm"]
