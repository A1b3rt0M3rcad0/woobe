from __future__ import annotations

from collections.abc import Callable

from modules.agent.application.interfaces.execution_strategy import (
    ExecutionStrategy,
    ExecutionStrategyResolver,
)
from modules.agent.infra.execution.strategies.standard import StandardExecutionStrategy


_BUILTIN_EXECUTION_STRATEGY_FACTORIES: dict[
    str,
    Callable[[], ExecutionStrategy],
] = {
    "standard": StandardExecutionStrategy,
}


def builtin_execution_strategy_names() -> frozenset[str]:
    """Expose implemented built-in identities without coupling infra to app metadata."""

    return frozenset(_BUILTIN_EXECUTION_STRATEGY_FACTORIES)


class BuiltinExecutionStrategyResolver:
    """Resolve concrete built-in strategies behind the Application runtime contract."""

    __slots__ = ("_strategies",)

    def __init__(self) -> None:
        self._strategies: dict[str, ExecutionStrategy] = {
            name: factory()
            for name, factory in _BUILTIN_EXECUTION_STRATEGY_FACTORIES.items()
        }

    def resolve(self, name: str) -> ExecutionStrategy:
        strategy = self._strategies.get(name)
        if strategy is None:
            raise ValueError(f"Unsupported execution strategy: {name}")
        return strategy


def build_execution_strategy_resolver() -> ExecutionStrategyResolver:
    return BuiltinExecutionStrategyResolver()
