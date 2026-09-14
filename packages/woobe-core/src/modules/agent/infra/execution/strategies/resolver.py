from __future__ import annotations

from modules.agent.application.interfaces.execution_strategy import (
    ExecutionStrategy,
    ExecutionStrategyResolver,
)
from modules.agent.infra.execution.strategies.standard import StandardExecutionStrategy


class BuiltinExecutionStrategyResolver:
    """Small explicit resolver for Woobe built-in Agent execution strategies."""

    __slots__ = ("_strategies",)

    def __init__(self) -> None:
        self._strategies: dict[str, ExecutionStrategy] = {
            "standard": StandardExecutionStrategy(),
        }

    def resolve(self, name: str) -> ExecutionStrategy:
        strategy = self._strategies.get(name)
        if strategy is None:
            raise ValueError(f"Unsupported execution strategy: {name}")
        return strategy


def build_execution_strategy_resolver() -> ExecutionStrategyResolver:
    return BuiltinExecutionStrategyResolver()
