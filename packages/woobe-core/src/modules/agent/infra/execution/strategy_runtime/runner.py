from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.agent.application.interfaces.execution import (
    ExecutionSuspension,
    InstrumentedExecution,
    InstrumentedExecutionError,
)
from modules.agent.application.interfaces.execution_strategy import (
    ExecutionStrategy,
    ExecutionStrategyRequest,
)
from modules.agent.application.strategy_sdk import (
    Completed,
    StrategyExecutionError,
    StrategyModelResult,
    Suspended,
)
from modules.agent.infra.execution.capabilities.bundle import ExecutionCapabilities
from modules.agent.infra.execution.strategy_runtime.builder import (
    BuiltStrategyContext,
    BuiltStrategyExecution,
    build_strategy_context_from_capabilities,
    build_strategy_execution,
)


def _apply_completed_result(
    execution: InstrumentedExecution,
    outcome: Completed,
    *,
    raw_model_result: Any | None,
) -> None:
    result = outcome.result
    execution.result = (
        raw_model_result if isinstance(result, StrategyModelResult) else result
    )


async def execute_strategy(
    strategy: ExecutionStrategy[Any],
    request: ExecutionStrategyRequest,
) -> InstrumentedExecution:
    built = build_strategy_execution(strategy=strategy, request=request)
    try:
        outcome = await strategy.execute(built.context)
    except StrategyExecutionError as exc:
        runtime_error = exc.__cause__
        if isinstance(runtime_error, InstrumentedExecutionError):
            raise runtime_error from exc
        raise
    if isinstance(outcome, Suspended):
        built.runtime_state.execution.suspension = ExecutionSuspension(
            reason=outcome.reason.value,
            operation_ref=outcome.operation_ref,
            metadata=dict(outcome.metadata or {}),
        )
        return built.runtime_state.execution
    if not isinstance(outcome, Completed):
        raise RuntimeError("Execution Strategy returned an unsupported outcome")

    _apply_completed_result(
        built.runtime_state.execution,
        outcome,
        raw_model_result=built.runtime_state.last_model_message,
    )
    return built.runtime_state.execution


async def execute_strategy_with_capabilities(
    *,
    strategy: ExecutionStrategy[Any],
    capabilities: ExecutionCapabilities,
    messages: list[Any],
    initial_phase: str,
    final_json_instruction: str | None,
    final_model: Any | None = None,
    final_model_factory: Any | None = None,
    bootstrap: dict[str, Any] | None = None,
) -> tuple[InstrumentedExecution, int]:
    """Compatibility bridge for legacy focused callers without duplicating algorithms."""

    built = build_strategy_context_from_capabilities(
        strategy=strategy,
        capabilities=capabilities,
        messages=messages,
        initial_phase=initial_phase,
        final_model=final_model,
        final_model_factory=final_model_factory,
        final_json_instruction=final_json_instruction,
        bootstrap=bootstrap,
    )
    try:
        outcome = await strategy.execute(built.context)
    except StrategyExecutionError as exc:
        runtime_error = exc.__cause__
        if isinstance(runtime_error, InstrumentedExecutionError):
            raise runtime_error from exc
        raise
    if isinstance(outcome, Suspended):
        built.runtime_state.execution.suspension = ExecutionSuspension(
            reason=outcome.reason.value,
            operation_ref=outcome.operation_ref,
            metadata=dict(outcome.metadata or {}),
        )
        return built.runtime_state.execution, built.runtime_state.call_index
    if not isinstance(outcome, Completed):
        raise RuntimeError("Execution Strategy returned an unsupported outcome")

    _apply_completed_result(
        built.runtime_state.execution,
        outcome,
        raw_model_result=built.runtime_state.last_model_message,
    )
    return built.runtime_state.execution, built.runtime_state.call_index


@dataclass(frozen=True, slots=True)
class StrategyExecutionRunner:
    strategy: ExecutionStrategy[Any]

    async def execute(
        self,
        request: ExecutionStrategyRequest,
    ) -> InstrumentedExecution:
        return await execute_strategy(self.strategy, request)
