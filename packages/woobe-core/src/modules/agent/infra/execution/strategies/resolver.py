from __future__ import annotations

from collections.abc import Callable

from modules.agent.application.interfaces.execution_strategy import (
    ExecutableExecutionStrategy,
    ExecutionStrategyDefinition,
    ExecutionStrategyResolver,
)
from modules.agent.infra.execution.strategies.standard import (
    build_standard_strategy_definition,
)
from modules.agent.infra.execution.strategy_runtime.runner import StrategyExecutionRunner


_BUILTIN_EXECUTION_STRATEGY_DEFINITIONS: dict[
    str,
    Callable[[], ExecutionStrategyDefinition],
] = {
    "standard": build_standard_strategy_definition,
}


def builtin_execution_strategy_names() -> frozenset[str]:
    """Expose implemented built-in identities without coupling infra to app metadata."""

    return frozenset(_BUILTIN_EXECUTION_STRATEGY_DEFINITIONS)


class BuiltinExecutionStrategyResolver:
    """Resolve built-in algorithms behind the outer runtime execution contract."""

    __slots__ = ("_strategies",)

    def __init__(self) -> None:
        self._strategies: dict[str, ExecutableExecutionStrategy] = {
            name: StrategyExecutionRunner(factory())
            for name, factory in _BUILTIN_EXECUTION_STRATEGY_DEFINITIONS.items()
        }

    def resolve(self, name: str) -> ExecutableExecutionStrategy:
        strategy = self._strategies.get(name)
        if strategy is None:
            raise ValueError(f"Unsupported execution strategy: {name}")
        return strategy


def build_execution_strategy_resolver() -> ExecutionStrategyResolver:
    return BuiltinExecutionStrategyResolver()
