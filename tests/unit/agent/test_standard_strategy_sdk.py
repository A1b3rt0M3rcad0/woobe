from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.strategy_sdk import (
    Completed,
    StrategyModelResult,
    StrategyToolBatch,
    Suspended,
    SuspensionReason,
)
from modules.agent.infra.execution.strategies.standard.phases import StandardPhase
from modules.agent.infra.execution.strategies.standard.policy import StandardExecutionPolicy
from modules.agent.infra.execution.strategies.standard.state import StandardExecutionState
from modules.agent.infra.execution.strategies.standard.strategy import StandardExecutionStrategy


class _Model:
    def __init__(self, results):
        self.results = list(results)
        self.phases: list[str] = []

    async def invoke(self, *, messages, phase):
        del messages
        self.phases.append(str(getattr(phase, "value", phase)))
        return self.results.pop(0)

    async def finalize(self, *, messages, reason, phase):
        del messages, reason
        self.phases.append(str(getattr(phase, "value", phase)))
        return self.results.pop(0)


class _Tools:
    def __init__(self, batches):
        self.batches = list(batches)
        self.calls: list[tuple[dict, ...]] = []

    async def execute_many(self, tool_calls):
        self.calls.append(tuple(tool_calls))
        return self.batches.pop(0)


class _Context:
    def __init__(self, *, state, model, tools):
        self.state = state
        self.model = model
        self.tools = tools
        self.checkpoints = 0

    async def checkpoint(self):
        self.checkpoints += 1

    def complete(self, result):
        message = result.message if isinstance(result, StrategyModelResult) else result
        return Completed(InstrumentedExecution(result=message))

    def suspend(self, *, reason, operation_ref=None, metadata=None):
        return Suspended(reason=reason, operation_ref=operation_ref, metadata=metadata)


def _model_result(*, content="", tool_calls=None):
    return StrategyModelResult(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls or []))
    )


@pytest.mark.asyncio
async def test_standard_algorithm_is_expressed_only_with_strategy_context_primitives() -> None:
    first = _model_result(
        tool_calls=[{"id": "call-1", "name": "lookup", "args": {}}]
    )
    final = _model_result(content="done")
    tool_message = SimpleNamespace(content="tool-result")
    batch = StrategyToolBatch(
        results=({"success": True},),
        messages=(tool_message,),
        has_failures=False,
    )
    state = StandardExecutionState(
        messages=[SimpleNamespace(content="user")],
        next_phase=StandardPhase.CAPABILITY_RESPONSE_GENERATION.value,
    )
    ctx = _Context(state=state, model=_Model([first, final]), tools=_Tools([batch]))

    outcome = await StandardExecutionStrategy(StandardExecutionPolicy()).execute(ctx)

    assert isinstance(outcome, Completed)
    assert outcome.execution.result.content == "done"
    assert ctx.checkpoints == 1
    assert state.tool_round == 1
    assert state.consecutive_failures == 0
    assert state.messages[-1] is tool_message
    assert ctx.model.phases == [
        "capability_response_generation",
        "tool_followup_1",
    ]


@pytest.mark.asyncio
async def test_standard_algorithm_can_return_suspension_without_run_lifecycle_access() -> None:
    first = _model_result(
        tool_calls=[{"id": "call-1", "name": "long_job", "args": {}}]
    )
    batch = StrategyToolBatch(
        results=(),
        messages=(),
        has_failures=False,
        requires_suspension=True,
        suspension_reason=SuspensionReason.ASYNC_TOOL,
        operation_ref="job-123",
    )
    state = StandardExecutionState(
        messages=[],
        next_phase=StandardPhase.CAPABILITY_RESPONSE_GENERATION.value,
    )
    ctx = _Context(state=state, model=_Model([first]), tools=_Tools([batch]))

    outcome = await StandardExecutionStrategy(StandardExecutionPolicy()).execute(ctx)

    assert isinstance(outcome, Suspended)
    assert outcome.reason is SuspensionReason.ASYNC_TOOL
    assert outcome.operation_ref == "job-123"
    assert ctx.checkpoints == 1
