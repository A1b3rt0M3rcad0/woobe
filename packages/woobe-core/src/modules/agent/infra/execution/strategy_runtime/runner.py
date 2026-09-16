from __future__ import annotations

from dataclasses import dataclass

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_strategy import (
    ExecutionStrategyDefinition,
    ExecutionStrategyRequest,
)
from modules.agent.application.strategy_sdk import Completed, Suspended
from modules.agent.infra.execution.capabilities.result_finalization import (
    finalize_execution_result,
)
from modules.agent.infra.execution.strategy_runtime.builder import (
    build_strategy_execution,
)


async def execute_strategy_definition(
    definition: ExecutionStrategyDefinition,
    request: ExecutionStrategyRequest,
) -> InstrumentedExecution:
    built = build_strategy_execution(definition=definition, request=request)
    strategy = definition.strategy_factory()
    outcome = await strategy.execute(built.context)
    if isinstance(outcome, Suspended):
        raise RuntimeError(
            "Execution Strategy suspension is defined by the internal SDK but the outer "
            "Agent Run WAITING lifecycle is not enabled yet"
        )
    if not isinstance(outcome, Completed):
        raise RuntimeError("Execution Strategy returned an unsupported outcome")
    return await finalize_execution_result(
        prepared=built.prepared,
        execution=outcome.execution,
        call_index=built.runtime_state.call_index,
    )


@dataclass(frozen=True, slots=True)
class StrategyExecutionRunner:
    definition: ExecutionStrategyDefinition

    async def execute(
        self,
        request: ExecutionStrategyRequest,
    ) -> InstrumentedExecution:
        return await execute_strategy_definition(self.definition, request)
