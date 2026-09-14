from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_strategy import (
    ExecutionStrategy,
    ExecutionStrategyRequest,
)
from modules.agent.infra.execution.capabilities.bundle import (
    build_execution_capabilities,
)
from modules.agent.infra.execution.capabilities.preparation import prepare_execution
from modules.agent.infra.execution.capabilities.result_finalization import (
    finalize_execution_result,
)
from modules.agent.infra.execution.capabilities.state import StrategyExecutionState


class _TwoPassToolStrategy:
    """Test-only Strategy proving that orchestration can live outside the legacy runner."""

    async def execute(self, request: ExecutionStrategyRequest) -> InstrumentedExecution:
        prepared = prepare_execution(request)
        capabilities = build_execution_capabilities(
            request=request,
            prepared=prepared,
        )
        state = StrategyExecutionState(messages=list(prepared.messages))

        for iteration in range(1, 3):
            result, call = await capabilities.model.invoke(
                model=prepared.model,
                messages=state.messages,
                phase=f"test_multi_loop_{iteration}",
                call_index=iteration,
            )
            state.iteration = iteration
            state.record_model_result(result=result, call=call)
            tool_calls = list(getattr(result, "tool_calls", None) or [])
            if not tool_calls:
                break
            state.messages.append(result)
            batch = await capabilities.tools.execute_many(tool_calls)
            state.record_tool_batch(batch)

        execution = state.finish()
        return await finalize_execution_result(
            request=request,
            prepared=prepared,
            execution=execution,
            call_index=state.call_index,
        )


class _FakeBoundModel:
    def bind_tools(self, _tools, *, tool_choice):
        assert tool_choice == "auto"
        return self


class _FakeModelFactory:
    def __init__(self) -> None:
        self.model = _FakeBoundModel()

    def create_chat_model(self, **_kwargs):
        return self.model


def _request(execute_single_tool) -> ExecutionStrategyRequest:
    return ExecutionStrategyRequest(
        llm_factory=_FakeModelFactory(),
        execute_single_tool=execute_single_tool,
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
        has_tools=True,
        agent_tools=[
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search",
                    "parameters": {"type": "object"},
                },
            }
        ],
        tool_name_to_id={"search": "tool-id"},
        messages=["user-message"],
        context_assembler=None,
    )


@pytest.mark.asyncio
async def test_test_strategy_implements_contract_and_owns_multi_step_loop(
    monkeypatch,
) -> None:
    model_calls: list[int] = []
    executed_tools: list[str] = []

    async def fake_invoke_llm(**kwargs):
        call_index = kwargs["call_index"]
        model_calls.append(call_index)
        result = (
            SimpleNamespace(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "search",
                        "args": {"q": "woobe"},
                    }
                ],
            )
            if call_index == 1
            else SimpleNamespace(content="final", tool_calls=[])
        )
        return (
            result,
            {
                "call_index": call_index,
                "phase": kwargs["phase"],
                "occurred_at": f"model-{call_index}",
            },
        )

    async def fake_execute_tool_call(**kwargs):
        executed_tools.append(kwargs["resolved_tool_id"])
        return (
            SimpleNamespace(duration_ms=2, success=True),
            SimpleNamespace(content="tool-result"),
            {"occurred_at": "tool-1"},
        )

    async def execute_single_tool(_tool_call, _tool_id):
        return {}

    monkeypatch.setattr(
        "modules.agent.infra.execution.capabilities.model_invocation.invoke_llm",
        fake_invoke_llm,
    )
    monkeypatch.setattr(
        "modules.agent.infra.execution.capabilities.tool_execution.execute_tool_call",
        fake_execute_tool_call,
    )

    strategy = _TwoPassToolStrategy()
    assert isinstance(strategy, ExecutionStrategy)

    execution = await strategy.execute(_request(execute_single_tool))

    assert model_calls == [1, 2]
    assert executed_tools == ["tool-id"]
    assert execution.result.content == "final"
    assert len(execution.llm_calls) == 2
    assert len(execution.tool_calls) == 1
    assert [item["kind"] for item in execution.timeline] == ["llm", "tool", "llm"]
