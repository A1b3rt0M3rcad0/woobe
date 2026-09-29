import pytest

from modules.agent.application.execution_strategy_registry import (
    DEFAULT_EXECUTION_STRATEGY,
    SUPPORTED_EXECUTION_STRATEGIES,
    DuplicateExecutionStrategyError,
    ExecutionStrategyDescriptor,
    UnknownExecutionStrategyError,
    build_execution_strategy_registry,
    list_execution_strategies,
)
from modules.agent.application.interfaces.execution_strategy import (
    ExecutableExecutionStrategy,
)
from modules.agent.infra.execution.strategies.resolver import (
    BuiltinExecutionStrategyResolver,
    builtin_execution_strategy_names,
)


def test_execution_strategy_catalog_is_backend_owned_and_complete() -> None:
    descriptors = list_execution_strategies()

    assert descriptors
    assert {item["name"] for item in descriptors} == SUPPORTED_EXECUTION_STRATEGIES
    assert descriptors[0]["name"] == DEFAULT_EXECUTION_STRATEGY
    assert descriptors[0]["is_default"] is True
    assert sum(item["is_default"] is True for item in descriptors) == 1

    for descriptor in descriptors:
        assert descriptor["display_name"]
        assert descriptor["description"]
        assert descriptor["behavior"]
        assert descriptor["recommended_for"]
        assert descriptor["capabilities"]
        assert descriptor["limitations"]
        assert descriptor["compatibility"]


def test_registry_owns_strategy_metadata_contract() -> None:
    registry = build_execution_strategy_registry()
    descriptor = registry.get(DEFAULT_EXECUTION_STRATEGY)

    assert descriptor.name == "standard"
    assert descriptor.display_name == "Standard"
    assert descriptor.behavior
    assert descriptor.capabilities
    assert descriptor.limitations
    assert registry.current_default() == descriptor


def test_registry_rejects_duplicate_and_unknown_strategies() -> None:
    registry = build_execution_strategy_registry()

    duplicate = ExecutionStrategyDescriptor(
        name="standard",
        display_name="Duplicate",
        description="Duplicate descriptor used only by this test.",
        behavior="Would conflict with the registered Standard strategy.",
        recommended_for=("Tests.",),
        capabilities=("None.",),
        limitations=("Not selectable.",),
        compatibility=registry.get("standard").compatibility,
    )

    with pytest.raises(DuplicateExecutionStrategyError):
        registry.register(duplicate)

    with pytest.raises(UnknownExecutionStrategyError):
        registry.get("missing")


def test_backend_catalog_and_runtime_resolver_expose_same_strategy_names() -> None:
    assert builtin_execution_strategy_names() == SUPPORTED_EXECUTION_STRATEGIES


def test_every_catalog_strategy_is_resolvable_by_runtime() -> None:
    resolver = BuiltinExecutionStrategyResolver()

    for descriptor in list_execution_strategies():
        assert isinstance(
            resolver.resolve(str(descriptor["name"])),
            ExecutableExecutionStrategy,
        )
