from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.agent.application import execution_strategy_config
from modules.agent.application.interfaces.execution import InstrumentedExecution
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


class _MapResolver:
    def __init__(self) -> None:
        self.strategies = {
            "standard": _NamedStrategy("standard"),
            "test_iterative": _NamedStrategy("test_iterative"),
        }
        self.names: list[str] = []

    def resolve(self, name: str) -> _NamedStrategy:
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
