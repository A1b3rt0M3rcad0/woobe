from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_strategy import (
    ExecutionStrategyDefinition,
    ExecutionStrategyRequest,
)
from modules.agent.application.strategy_sdk import (
    StrategyInitialization,
    StrategyResumeSnapshot,
)
from modules.agent.infra.execution.capabilities.bundle import (
    ExecutionCapabilities,
    build_execution_capabilities,
)
from modules.agent.infra.execution.capabilities.preparation import (
    PreparedExecution,
    prepare_execution,
)
from modules.agent.infra.execution.strategy_runtime.checkpoint import (
    RuntimeStrategyCheckpoint,
)
from modules.agent.infra.execution.strategy_runtime.context import RuntimeStrategyContext
from modules.agent.infra.execution.strategy_runtime.model import RuntimeStrategyModel
from modules.agent.infra.execution.strategy_runtime.runtime_state import StrategyRuntimeState
from modules.agent.infra.execution.strategy_runtime.tools import RuntimeStrategyTools


@dataclass(frozen=True, slots=True)
class BuiltStrategyContext:
    context: RuntimeStrategyContext[Any]
    runtime_state: StrategyRuntimeState


@dataclass(frozen=True, slots=True)
class BuiltStrategyExecution:
    context: RuntimeStrategyContext[Any]
    runtime_state: StrategyRuntimeState
    prepared: PreparedExecution


def _resume_snapshot(value: Any) -> StrategyResumeSnapshot | None:
    if value is None:
        return None
    return StrategyResumeSnapshot(
        phase=value.phase,
        cursor=dict(value.cursor),
        capability_messages=tuple(value.capability_messages),
        execution=value.execution,
    )


def build_strategy_context_from_capabilities(
    *,
    definition: ExecutionStrategyDefinition[Any],
    capabilities: ExecutionCapabilities,
    messages: list[Any],
    initial_phase: str,
    final_model: Any | None = None,
    final_model_factory: Any | None = None,
    final_json_instruction: str | None = None,
    bootstrap: dict[str, Any] | None = None,
) -> BuiltStrategyContext:
    resume = capabilities.recovery.load()
    snapshot = _resume_snapshot(resume)
    cursor = dict(snapshot.cursor) if snapshot is not None else {}
    try:
        next_call_index = int(cursor.get("next_call_index") or 1)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Execution Strategy recovery cursor has invalid call index") from exc
    if next_call_index <= 0:
        raise RuntimeError("Execution Strategy recovery cursor has invalid call index")

    runtime_state = StrategyRuntimeState(
        execution=(
            snapshot.execution if snapshot is not None else InstrumentedExecution(result=None)
        ),
        call_index=max(0, next_call_index - 1),
    )
    initialization = StrategyInitialization(
        messages=tuple(messages),
        initial_phase=initial_phase,
        bootstrap=dict(bootstrap or {}),
    )
    state = definition.state_factory.create(initialization, snapshot)
    checkpoint = RuntimeStrategyCheckpoint(
        recovery=capabilities.recovery,
        runtime_state=runtime_state,
        state_codec=definition.state_codec,
        base_message_count=len(messages),
    )
    context = RuntimeStrategyContext(
        state=state,
        model=RuntimeStrategyModel(
            capability=capabilities.model,
            runtime_state=runtime_state,
            base_messages=messages,
            final_model=final_model,
            final_model_factory=final_model_factory,
            final_json_instruction=final_json_instruction,
        ),
        tools=RuntimeStrategyTools(
            capability=capabilities.tools,
            runtime_state=runtime_state,
        ),
        checkpoint=checkpoint,
        runtime_state=runtime_state,
    )
    return BuiltStrategyContext(context=context, runtime_state=runtime_state)


def build_strategy_execution(
    *,
    definition: ExecutionStrategyDefinition[Any],
    request: ExecutionStrategyRequest,
) -> BuiltStrategyExecution:
    prepared = prepare_execution(request)
    capabilities = build_execution_capabilities(
        prepared=prepared,
        strategy_name=definition.name,
    )
    built = build_strategy_context_from_capabilities(
        definition=definition,
        capabilities=capabilities,
        messages=prepared.messages,
        initial_phase=prepared.initial_phase,
        final_model=prepared.final_model,
        final_model_factory=prepared.final_model_factory,
        final_json_instruction=prepared.final_json_instruction,
    )
    return BuiltStrategyExecution(
        context=built.context,
        runtime_state=built.runtime_state,
        prepared=prepared,
    )
