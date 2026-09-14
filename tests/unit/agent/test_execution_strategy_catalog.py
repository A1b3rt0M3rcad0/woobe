from modules.agent.application.execution_strategy_config import (
    DEFAULT_EXECUTION_STRATEGY,
    SUPPORTED_EXECUTION_STRATEGIES,
    list_execution_strategies,
)
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategy
from modules.agent.infra.execution.strategies.resolver import BuiltinExecutionStrategyResolver


def test_execution_strategy_catalog_is_backend_owned_and_complete() -> None:
    descriptors = list_execution_strategies()

    assert descriptors
    assert {item["name"] for item in descriptors} == SUPPORTED_EXECUTION_STRATEGIES
    assert descriptors[0]["name"] == DEFAULT_EXECUTION_STRATEGY
    assert descriptors[0]["is_default"] is True

    for descriptor in descriptors:
        assert descriptor["display_name"]
        assert descriptor["description"]
        assert descriptor["behavior"]
        assert descriptor["recommended_for"]
        assert descriptor["capabilities"]
        assert descriptor["limitations"]


def test_every_catalog_strategy_is_resolvable_by_runtime() -> None:
    resolver = BuiltinExecutionStrategyResolver()

    for descriptor in list_execution_strategies():
        assert isinstance(resolver.resolve(str(descriptor["name"])), ExecutionStrategy)
