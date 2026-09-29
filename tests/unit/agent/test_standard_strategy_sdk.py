from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from modules.agent.application.strategy_sdk import (
    Completed,
    ExecutionCheckpointBoundary,
    ExecutionPhase,
    ExecutionPolicy,
    ExecutionState,
    ExecutionStopReason,
    StrategyBootstrap,
    StrategyContextCompactionResult,
    StrategyKnowledgeResult,
    StrategyMessage,
    StrategyMessageRole,
    StrategyModelResult,
    StrategyToolBatch,
    StrategyToolCall,
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


@dataclass(frozen=True, slots=True)
class _Invocation:
    invocation_id: UUID
    phase: str
    tools: StrategyToolSelection


class _Knowledge:
    def __init__(self) -> None:
        self.calls: list[tuple[str | None, str | None]] = []

    async def retrieve(self, *, conversation, phase=None):
        self.calls.append((conversation, str(getattr(phase, "value", phase))))
        return StrategyKnowledgeResult(content=None)


class _Conversation:
    def __init__(self) -> None:
        self.current_user_message = StrategyMessage(
            id="user-current",
            role=StrategyMessageRole.USER,
            content="test query",
        )
        self.history = ()
        self.system_messages = ()
        self.assistant_messages = ()
        self.last_assistant_message = None
        self.messages = (self.current_user_message,)


class _ContextManager:
    def __init__(self) -> None:
        self.contributions = {}
        self.calls: list[tuple[str | None, StrategyToolSelection | None]] = []
        self.compaction_phases: list[str] = []
        self.knowledge_results = []

    def include_knowledge(self, result) -> None:
        self.knowledge_results.append(result)

    async def compact(self, *, phase=None):
        normalized_phase = str(getattr(phase, "value", phase))
        self.compaction_phases.append(normalized_phase)
        return StrategyContextCompactionResult(changed=False)

    async def prepare(self, *, phase=None, tools=None, target=None):
        del target
        normalized_phase = str(getattr(phase, "value", phase))
        self.calls.append((normalized_phase, tools))
        return _Invocation(
            invocation_id=uuid4(),
            phase=normalized_phase,
            tools=tools,
        )

    async def prepare_final(self, *, reason, phase, tools=None, target=None):
        del reason, target
        return await self.prepare(phase=phase, tools=tools)


class _Model:
    def __init__(self, results):
        self.results = list(results)
        self.phases: list[str] = []
        self.fallback_available = False

    async def invoke(self, invocation):
        self.phases.append(invocation.phase)
        return self.results.pop(0)

    async def finalize(self, invocation, *, reason):
        del reason
        self.phases.append(invocation.phase)
        return self.results.pop(0)


class _Tools:
    def __init__(self, batches):
        self.batches = list(batches)
        self.calls: list[tuple[StrategyToolCall, ...]] = []
        self.has_any = True

    def all(self) -> StrategyToolSelection:
        return StrategyToolSelection(mode=StrategyToolSelectionMode.ALL)

    def none(self) -> StrategyToolSelection:
        return StrategyToolSelection(mode=StrategyToolSelectionMode.NONE)

    async def execute_many(self, tool_calls):
        self.calls.append(tuple(tool_calls))
        return self.batches.pop(0)


class _Output:
    def has_public_output(self, result) -> bool:
        content = getattr(result, "content", None)
        return isinstance(content, str) and bool(content.strip())

    def requires_repair(self, _result) -> bool:
        return False

    async def repair(self, *_args, **_kwargs):
        raise AssertionError("Output repair must not run")


class _Context:
    def __init__(self, *, state, model, tools):
        self.state = state
        self.bootstrap = StrategyBootstrap()
        self.conversation = _Conversation()
        self.model = model
        self.tools = tools
        self.knowledge = _Knowledge()
        self.context = _ContextManager()
        self.output = _Output()
        self.checkpoints: list[ExecutionCheckpointBoundary] = []

    async def checkpoint(self, boundary=ExecutionCheckpointBoundary.TOOL):
        self.checkpoints.append(boundary)


def _model_result(*, content="", tool_calls=None):
    normalized = tuple(
        StrategyToolCall(
            id=item.get("id"),
            name=item["name"],
            arguments=item.get("args") or {},
        )
        for item in (tool_calls or [])
    )
    return StrategyModelResult(content=content, tool_calls=normalized)


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
        "preflight_resolved": False,
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
        results=(),
        has_failures=False,
    )
    state = StandardExecutionState(
        phase=StandardPhase.CAPABILITY_RESPONSE_GENERATION.value,
    )
    ctx = _Context(state=state, model=_Model([first, final]), tools=_Tools([batch]))

    outcome = await StandardExecutionStrategy().execute(ctx)

    assert isinstance(outcome, Completed)
    assert outcome.result.content == "done"
    assert ctx.checkpoints == [ExecutionCheckpointBoundary.TOOL]
    assert ctx.knowledge.calls == [(ctx.conversation, "knowledge_retrieval")]
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
    assert ctx.knowledge.calls == [(ctx.conversation, "knowledge_retrieval")]
    assert state.knowledge_resolved is True


@pytest.mark.asyncio
async def test_failed_knowledge_is_not_marked_resolved():
    state = StandardExecutionState()
    ctx = _Context(state=state, model=_Model([]), tools=_Tools([]))

    class FailingKnowledge:
        async def retrieve(self, *, conversation, phase):
            assert conversation is ctx.conversation
            raise RuntimeError("retrieval failed")

    ctx.knowledge = FailingKnowledge()
    with pytest.raises(RuntimeError, match="retrieval failed"):
        await StandardExecutionStrategy().execute(ctx)
    assert state.knowledge_resolved is False
