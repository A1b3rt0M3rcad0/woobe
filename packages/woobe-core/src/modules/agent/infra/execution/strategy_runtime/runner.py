from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_strategy import (
    ExecutionStrategy,
    ExecutionStrategyRequest,
)
from modules.agent.application.strategy_sdk import (
    Completed,
    ExecutionCheckpointBoundary,
    StrategyModelResult,
    Suspended,
)
from modules.agent.infra.execution.capabilities.bundle import ExecutionCapabilities
from modules.agent.infra.execution.capabilities.result_finalization import (
    finalize_execution_result,
)
from modules.agent.infra.execution.strategy_runtime.builder import (
    BuiltStrategyContext,
    BuiltStrategyExecution,
    build_strategy_context_from_capabilities,
    build_strategy_execution,
)


async def _run_preflight(built: BuiltStrategyContext | BuiltStrategyExecution) -> None:
    if built.preflight_tool_call is None:
        return
    await built.context.tools.execute_many([built.preflight_tool_call])
    await built.context.checkpoint(ExecutionCheckpointBoundary.PREFLIGHT)


def _apply_completed_result(
    execution: InstrumentedExecution,
    outcome: Completed,
) -> None:
    result = outcome.result
    execution.result = (
        result.message if isinstance(result, StrategyModelResult) else result
    )


async def execute_strategy(
    strategy: ExecutionStrategy[Any],
    request: ExecutionStrategyRequest,
) -> InstrumentedExecution:
    built = build_strategy_execution(strategy=strategy, request=request)
    await _run_preflight(built)
    outcome = await strategy.execute(built.context)
    if isinstance(outcome, Suspended):
        raise RuntimeError(
            "Execution Strategy suspension is defined by the internal SDK but the outer "
            "Agent Run WAITING lifecycle is not enabled yet"
        )
    if not isinstance(outcome, Completed):
        raise RuntimeError("Execution Strategy returned an unsupported outcome")

    _apply_completed_result(built.runtime_state.execution, outcome)
    return await finalize_execution_result(
        prepared=built.prepared,
        execution=built.runtime_state.execution,
        call_index=built.runtime_state.call_index,
    )


async def execute_strategy_with_capabilities(
    *,
    strategy: ExecutionStrategy[Any],
    capabilities: ExecutionCapabilities,
    messages: list[Any],
    initial_phase: str,
    final_json_instruction: str | None,
    communication_model: Any | None = None,
    communication_model_factory: Any | None = None,
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
        communication_model=communication_model,
        communication_model_factory=communication_model_factory,
        final_model=final_model,
        final_model_factory=final_model_factory,
        final_json_instruction=final_json_instruction,
        bootstrap=bootstrap,
    )
    await _run_preflight(built)
    outcome = await strategy.execute(built.context)
    if isinstance(outcome, Suspended):
        raise RuntimeError("Legacy Strategy execution does not support suspended outcomes")
    if not isinstance(outcome, Completed):
        raise RuntimeError("Execution Strategy returned an unsupported outcome")

    _apply_completed_result(built.runtime_state.execution, outcome)
    return built.runtime_state.execution, built.runtime_state.call_index


@dataclass(frozen=True, slots=True)
class StrategyExecutionRunner:
    strategy: ExecutionStrategy[Any]

    async def execute(
        self,
        request: ExecutionStrategyRequest,
    ) -> InstrumentedExecution:
        return await execute_strategy(self.strategy, request)
