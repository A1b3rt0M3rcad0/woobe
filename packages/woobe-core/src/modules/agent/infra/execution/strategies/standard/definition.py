from __future__ import annotations

from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyDefinition
from modules.agent.infra.execution.strategies.standard.policy import StandardExecutionPolicy
from modules.agent.infra.execution.strategies.standard.state import (
    StandardExecutionState,
    StandardStateCodec,
    StandardStateFactory,
)
from modules.agent.infra.execution.strategies.standard.strategy import (
    StandardExecutionStrategy,
)


def build_standard_strategy_definition() -> ExecutionStrategyDefinition[StandardExecutionState]:
    policy = StandardExecutionPolicy()
    return ExecutionStrategyDefinition(
        name="standard",
        strategy_factory=lambda: StandardExecutionStrategy(policy),
        state_factory=StandardStateFactory(),
        state_codec=StandardStateCodec(),
    )
