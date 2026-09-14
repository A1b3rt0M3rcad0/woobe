from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.agent.application import execution_strategy_config
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.infra.execution.instrumented_primary_mixin import (
    InstrumentedPrimaryExecutionMixin,
)
from modules.agent.infra.execution.release_runtime_resolver import ReleaseRuntimeResolver


class _NamedStrategy:
    def __init__(self, name: str) -> None:
        self.name = name
        self.requests: list[ExecutionStrategyRequest] = []

    async def execute(self, request: ExecutionStrategyRequest) -> InstrumentedExecution:
        self.requests.append(request)
        return InstrumentedExecution(
            result=SimpleNamespace(
                content=f"executed:{self.name}",
                usage_metadata=None,
            )
        )


class _MultiStepUsageStrategy:
    async def execute(self, _request: ExecutionStrategyRequest) -> InstrumentedExecution:
        calls = [
            {
                "call_id": "call-1",
                "call_index": 1,
                "phase": "reason_1",
                "status": "success",
                "occurred_at": "2026-09-14T18:00:00+00:00",
                "input_tokens": 10,
                "output_tokens": 4,
                "total_tokens": 14,
                "usage_complete": True,
            },
            {
                "call_id": "call-2",
                "call_index": 2,
                "phase": "reason_2",
                "status": "success",
                "occurred_at": "2026-09-14T18:00:01+00:00",
                "input_tokens": 8,
                "output_tokens": 3,
                "total_tokens": 11,
                "usage_complete": True,
            },
        ]
        return InstrumentedExecution(
            result=SimpleNamespace(content="multi-step", usage_metadata=None),
            llm_calls=calls,
            timeline=[
                {"kind": "llm", "occurred_at": call["occurred_at"], "payload": call}
                for call in calls
            ],
        )


class _MapResolver:
    def __init__(self) -> None:
        self.strategies = {
            "standard": _NamedStrategy("standard"),
            "test_iterative": _NamedStrategy("test_iterative"),
        }
        self.names: list[str] = []

    def resolve(self, name: str):
        self.names.append(name)
        return self.strategies[name]


class _Runtime(InstrumentedPrimaryExecutionMixin):
    _llm_factory = object()
    _context_assembler = None

    async def _execute_single_tool(self, tool_call: dict, tool_id: str) -> dict:
        return {"tool_call": tool_call, "tool_id": tool_id}

    def _clean_json_answer(self, answer: str) -> str:
        return answer


async def _execute(runtime: _Runtime, agent) -> str:
    result, _tools, _called, _repair = await runtime._execute_llm(
        agent=agent,
        api_key="secret",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=False,
        agent_tools=[],
        tool_name_to_id={},
        messages=["hello"],
    )
    return result.content


@pytest.mark.asyncio
async def test_two_agents_can_select_different_strategy_algorithms(monkeypatch) -> None:
    monkeypatch.setattr(
        execution_strategy_config,
        "SUPPORTED_EXECUTION_STRATEGIES",
        frozenset({"standard", "test_iterative"}),
    )
    resolver = _MapResolver()
    runtime = _Runtime()
    runtime.configure_execution_strategy_resolver(resolver)

    standard_agent = SimpleNamespace(
        settings={"runtime_config": {"execution_strategy": "standard"}},
    )
    iterative_agent = SimpleNamespace(
        settings={"runtime_config": {"execution_strategy": "test_iterative"}},
    )

    assert await _execute(runtime, standard_agent) == "executed:standard"
    assert await _execute(runtime, iterative_agent) == "executed:test_iterative"
    assert resolver.names == ["standard", "test_iterative"]


@pytest.mark.asyncio
async def test_frozen_release_snapshot_selects_non_standard_test_strategy(monkeypatch) -> None:
    monkeypatch.setattr(
        execution_strategy_config,
        "SUPPORTED_EXECUTION_STRATEGIES",
        frozenset({"standard", "test_iterative"}),
    )
    resolver = _MapResolver()
    runtime = _Runtime()
    runtime.configure_execution_strategy_resolver(resolver)
    agent = SimpleNamespace(
        settings={"runtime_config": {"execution_strategy": "standard"}},
    )

    ReleaseRuntimeResolver._apply_runtime_config_snapshot(
        agent,
        {"execution_strategy": "test_iterative"},
    )

    assert await _execute(runtime, agent) == "executed:test_iterative"
    assert resolver.names == ["test_iterative"]
    assert agent.settings["runtime_config"] == {
        "execution_strategy": "test_iterative"
    }


@pytest.mark.asyncio
async def test_multi_step_strategy_keeps_usage_and_timeline_visible_to_runtime(monkeypatch) -> None:
    monkeypatch.setattr(
        execution_strategy_config,
        "SUPPORTED_EXECUTION_STRATEGIES",
        frozenset({"standard", "test_iterative"}),
    )
    resolver = _MapResolver()
    resolver.strategies["test_iterative"] = _MultiStepUsageStrategy()
    runtime = _Runtime()
    runtime.configure_execution_strategy_resolver(resolver)
    agent = SimpleNamespace(
        settings={"runtime_config": {"execution_strategy": "test_iterative"}},
    )
    context = new_execution_context()
    token = current_execution.set(context)
    try:
        result, tools, called, repair = await runtime._execute_llm(
            agent=agent,
            api_key="secret",
            base_url=None,
            response_format={},
            json_enabled=False,
            has_tools=False,
            agent_tools=[],
            tool_name_to_id={},
            messages=["hello"],
        )
    finally:
        current_execution.reset(token)

    assert result.content == "multi-step"
    assert result.usage_metadata == {
        "input_tokens": 18,
        "output_tokens": 7,
        "total_tokens": 25,
    }
    assert tools == []
    assert called is False
    assert repair is None
    assert context.execution_strategy == "test_iterative"
    assert context.execution is not None
    assert len(context.execution.llm_calls) == 2
    assert [item["payload"]["phase"] for item in context.execution.timeline] == [
        "reason_1",
        "reason_2",
    ]
