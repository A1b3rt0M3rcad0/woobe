from __future__ import annotations

from collections.abc import Callable

from modules.agent.application.interfaces.execution_strategy import (
    ExecutableExecutionStrategy,
    ExecutionStrategy,
    ExecutionStrategyResolver,
)
from modules.agent.infra.execution.strategies.scientific_method import (
    ScientificMethodExecutionStrategy,
)
from modules.agent.infra.execution.strategies.standard import StandardExecutionStrategy
from modules.agent.infra.execution.strategy_runtime.runner import StrategyExecutionRunner


_BUILTIN_EXECUTION_STRATEGY_FACTORIES: dict[
    str,
    Callable[[], ExecutionStrategy],
] = {
    StandardExecutionStrategy.name: StandardExecutionStrategy,
    ScientificMethodExecutionStrategy.name: ScientificMethodExecutionStrategy,
}


def builtin_execution_strategy_names() -> frozenset[str]:
    return frozenset(_BUILTIN_EXECUTION_STRATEGY_FACTORIES)


class BuiltinExecutionStrategyResolver:
    """Resolve built-in algorithms behind the outer runtime execution contract."""

    __slots__ = ("_strategies",)

    def __init__(self) -> None:
        self._strategies: dict[str, ExecutableExecutionStrategy] = {
            name: StrategyExecutionRunner(factory())
            for name, factory in _BUILTIN_EXECUTION_STRATEGY_FACTORIES.items()
        }

    def resolve(self, name: str) -> ExecutableExecutionStrategy:
        strategy = self._strategies.get(name)
        if strategy is None:
            raise ValueError(f"Unsupported execution strategy: {name}")
        return strategy


def build_execution_strategy_resolver() -> ExecutionStrategyResolver:
    return BuiltinExecutionStrategyResolver()
