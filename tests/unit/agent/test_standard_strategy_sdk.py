from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.strategy_sdk import (
    Completed,
    ExecutionCheckpointBoundary,
    ExecutionPhase,
    ExecutionPolicy,
    ExecutionState,
    ExecutionStopReason,
    StrategyInvocationContext,
    StrategyKnowledgeResult,
    StrategyModelResult,
    StrategyToolBatch,
    StrategyToolSelection,
    StrategyToolSelectionMode,
    Suspended,
    SuspensionReason,
)
from modules.agent.infra.execution.strategies.standard import (
    StandardExecutionPolicy,
    StandardExecutionState,
    StandardExecutionStrategy,
    StandardPhase,
    StandardStopReason,
)


class _Knowledge:
    def __init__(self) -> None:
        self.calls: list[str | None] = []

    async def retrieve(self, *, query=None, phase=None):
        del query
        self.calls.append(str(getattr(phase, "value", phase)))
        return StrategyKnowledgeResult(content=None)


class _ContextManager:
    def __init__(self) -> None:
        self.contributions = {}
        self.calls: list[tuple[str | None, StrategyToolSelection | None]] = []

    def has(self, key: str) -> bool:
        return key in self.contributions

    def set(self, contribution) -> None:
        self.contributions[contribution.key] = contribution

    def remove(self, key: str) -> None:
        self.contributions.pop(key, None)

    async def assemble(self, *, phase=None, tools=None):
        normalized_phase = str(getattr(phase, "value", phase))
        self.calls.append((normalized_phase, tools))
        return StrategyInvocationContext(
            invocation_id=uuid4(),
            messages=(),
            snapshot=None,
        )


class _Model:
    def __init__(self, results):
        self.results = list(results)
        self.phases: list[str] = []

    async def invoke(self, *, context=None, tools=None, phase=None):
        del context, tools
        self.phases.append(str(getattr(phase, "value", phase)))
        return self.results.pop(0)

    async def finalize(self, *, reason, phase, context=None, tools=None):
        del reason, context, tools
        self.phases.append(str(getattr(phase, "value", phase)))
        return self.results.pop(0)


class _Tools:
    def __init__(self, batches):
        self.batches = list(batches)
        self.calls: list[tuple[dict, ...]] = []

    def all(self) -> StrategyToolSelection:
        return StrategyToolSelection(mode=StrategyToolSelectionMode.ALL)

    def none(self) -> StrategyToolSelection:
        return StrategyToolSelection(mode=StrategyToolSelectionMode.NONE)

    def select(self, *names: str) -> StrategyToolSelection:
        return StrategyToolSelection(
            mode=StrategyToolSelectionMode.EXPLICIT,
            names=tuple(names),
        )

    async def execute_many(self, tool_calls):
        self.calls.append(tuple(tool_calls))
        return self.batches.pop(0)


class _Context:
    def __init__(self, *, state, model, tools):
        self.state = state
        self.model = model
        self.tools = tools
        self.knowledge = _Knowledge()
        self.context = _ContextManager()
        self.checkpoints: list[ExecutionCheckpointBoundary] = []

    async def checkpoint(self, boundary=ExecutionCheckpointBoundary.TOOL):
        self.checkpoints.append(boundary)


def _model_result(*, content="", tool_calls=None):
    return StrategyModelResult(
        message=SimpleNamespace(content=content, tool_calls=list(tool_calls or []))
    )


def test_standard_types_implement_shared_strategy_contracts() -> None:
    state = StandardExecutionState()
    policy = StandardExecutionPolicy()

    assert isinstance(state, ExecutionState)
    assert isinstance(policy, ExecutionPolicy)
    assert isinstance(StandardPhase.RESPONSE_GENERATION, ExecutionPhase)
    assert isinstance(StandardStopReason.CAPABILITY_ROUND_LIMIT, ExecutionStopReason)
    assert "messages" not in StandardExecutionState.model_fields
    assert state.model_dump(mode="json") == {
        "phase": None,
        "tool_round": 0,
        "consecutive_failures": 0,
        "knowledge_resolved": False,
        "stop_reason": None,
    }


@pytest.mark.asyncio
async def test_standard_algorithm_is_expressed_only_with_strategy_context_primitives() -> None:
    first = _model_result(
        tool_calls=[{"id": "call-1", "name": "lookup", "args": {}}]
    )
    final = _model_result(content="done")
    batch = StrategyToolBatch(
        results=({"success": True},),
        messages=(SimpleNamespace(content="tool-result"),),
        has_failures=False,
    )
    state = StandardExecutionState(
        phase=StandardPhase.CAPABILITY_RESPONSE_GENERATION.value,
    )
    ctx = _Context(state=state, model=_Model([first, final]), tools=_Tools([batch]))

    outcome = await StandardExecutionStrategy().execute(ctx)

    assert isinstance(outcome, Completed)
    assert outcome.result.message.content == "done"
    assert ctx.checkpoints == [ExecutionCheckpointBoundary.TOOL]
    assert ctx.knowledge.calls == ["knowledge_retrieval"]
    assert state.knowledge_resolved is True
    assert state.tool_round == 1
    assert state.consecutive_failures == 0
    assert state.phase == "tool_followup_1"
    assert ctx.model.phases == [
        "capability_response_generation",
        "tool_followup_1",
    ]
    assert [phase for phase, _tools in ctx.context.calls] == [
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
        phase=StandardPhase.CAPABILITY_RESPONSE_GENERATION.value,
    )
    ctx = _Context(state=state, model=_Model([first]), tools=_Tools([batch]))

    outcome = await StandardExecutionStrategy().execute(ctx)

    assert isinstance(outcome, Suspended)
    assert outcome.reason is SuspensionReason.ASYNC_TOOL
    assert outcome.operation_ref == "job-123"
    assert ctx.checkpoints == [ExecutionCheckpointBoundary.TOOL]
    assert ctx.knowledge.calls == ["knowledge_retrieval"]
    assert state.knowledge_resolved is True
