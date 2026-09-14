from __future__ import annotations

from modules.agent.application.execution_strategy_registry import (
    build_execution_strategy_registry,
)
from modules.agent.application.interfaces.execution_strategy import (
    ExecutionStrategy,
    ExecutionStrategyResolver,
)
from modules.agent.infra.execution.strategies.standard import StandardExecutionStrategy


class BuiltinExecutionStrategyResolver:
    """Resolve concrete built-in strategies registered by the backend catalog."""

    __slots__ = ("_strategies",)

    def __init__(self) -> None:
        self._strategies: dict[str, ExecutionStrategy] = {
            "standard": StandardExecutionStrategy(),
        }

        registered = {
            descriptor.name
            for descriptor in build_execution_strategy_registry().list_descriptors()
        }
        implemented = set(self._strategies)
        if registered != implemented:
            missing_implementations = sorted(registered - implemented)
            missing_descriptors = sorted(implemented - registered)
            raise RuntimeError(
                "Execution Strategy registry/resolver mismatch: "
                f"missing implementations={missing_implementations}, "
                f"missing descriptors={missing_descriptors}"
            )

    def resolve(self, name: str) -> ExecutionStrategy:
        strategy = self._strategies.get(name)
        if strategy is None:
            raise ValueError(f"Unsupported execution strategy: {name}")
        return strategy


def build_execution_strategy_resolver() -> ExecutionStrategyResolver:
    return BuiltinExecutionStrategyResolver()
