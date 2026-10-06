from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
from typing import Any
from modules.agent.application.strategy_configuration import (
    check_strategy_config_schema,
    empty_strategy_config_schema,
)

from modules.agent.application.interfaces.execution_strategy import (
    STANDARD_EXECUTION_COMPATIBILITY,
)
from modules.agent.application.interfaces.model_compatibility import (
    ExecutionStrategySpec,
)


DEFAULT_EXECUTION_STRATEGY = "standard"


@dataclass(frozen=True, slots=True)
class ExecutionStrategyDescriptor:
    """Backend-owned product contract for one selectable Agent execution algorithm."""

    name: str
    display_name: str
    description: str
    behavior: str
    recommended_for: tuple[str, ...]
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...]
    compatibility: ExecutionStrategySpec
    is_default: bool = False
    config_schema: dict[str, Any] = field(default_factory=empty_strategy_config_schema)
    config_schema_version: str = "1"

    def __post_init__(self) -> None:
        check_strategy_config_schema(self.config_schema, self.config_schema_version)
        object.__setattr__(self, "config_schema", deepcopy(self.config_schema))
        required_text = {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "behavior": self.behavior,
        }
        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"Execution Strategy descriptor {field_name} must not be empty"
                )

        required_lists = {
            "recommended_for": self.recommended_for,
            "capabilities": self.capabilities,
            "limitations": self.limitations,
        }
        for field_name, values in required_lists.items():
            if not values or any(not item.strip() for item in values):
                raise ValueError(
                    f"Execution Strategy descriptor {field_name} must contain non-empty values"
                )

        if self.compatibility.name != self.name:
            raise ValueError(
                "Execution Strategy compatibility name must match descriptor name"
            )

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "behavior": self.behavior,
            "recommended_for": list(self.recommended_for),
            "capabilities": list(self.capabilities),
            "limitations": list(self.limitations),
            "compatibility": self.compatibility.as_dict(),
            "is_default": self.is_default,
            "config_schema": deepcopy(self.config_schema),
            "config_schema_version": self.config_schema_version,
        }


class ExecutionStrategyRegistryError(ValueError):
    """Base error for deterministic Execution Strategy catalog failures."""


class DuplicateExecutionStrategyError(ExecutionStrategyRegistryError):
    pass


class UnknownExecutionStrategyError(ExecutionStrategyRegistryError):
    pass


class InvalidDefaultExecutionStrategyError(ExecutionStrategyRegistryError):
    pass


class ExecutionStrategyRegistry:
    """Explicit backend catalog of selectable Agent execution algorithms.

    Product metadata and semantic compatibility are application-owned. Concrete runtime
    implementations stay behind ExecutionStrategyResolver so this layer does not
    depend on infrastructure strategy classes.
    """

    __slots__ = ("_descriptors",)

    def __init__(self) -> None:
        self._descriptors: dict[str, ExecutionStrategyDescriptor] = {}

    def register(self, descriptor: ExecutionStrategyDescriptor) -> None:
        if descriptor.name in self._descriptors:
            raise DuplicateExecutionStrategyError(
                f"Execution Strategy already registered: {descriptor.name}"
            )
        self._descriptors[descriptor.name] = descriptor

    def contains(self, name: str) -> bool:
        return name in self._descriptors

    def get(self, name: str) -> ExecutionStrategyDescriptor:
        descriptor = self._descriptors.get(name)
        if descriptor is None:
            raise UnknownExecutionStrategyError(f"Unknown Execution Strategy: {name}")
        return descriptor

    def current_default(self) -> ExecutionStrategyDescriptor:
        defaults = [
            descriptor
            for descriptor in self._descriptors.values()
            if descriptor.is_default
        ]
        if len(defaults) != 1:
            raise InvalidDefaultExecutionStrategyError(
                "Execution Strategy registry must contain exactly one default"
            )
        return defaults[0]

    def list_descriptors(self) -> tuple[ExecutionStrategyDescriptor, ...]:
        return tuple(
            sorted(
                self._descriptors.values(),
                key=lambda descriptor: (
                    0 if descriptor.is_default else 1,
                    descriptor.display_name.lower(),
                    descriptor.name,
                ),
            )
        )


_STANDARD_COMPATIBILITY = STANDARD_EXECUTION_COMPATIBILITY


_STANDARD_DESCRIPTOR = ExecutionStrategyDescriptor(
    name="standard",
    display_name="Standard",
    description=(
        "General-purpose Woobe execution strategy for conversational language-model "
        "and capability orchestration."
    ),
    behavior=(
        "Invokes a compatible language model, executes bound capabilities when "
        "requested, feeds durable results back into the model, and continues until "
        "terminal output or runtime safety limits are reached."
    ),
    recommended_for=(
        "General-purpose conversational language Agents that need predictable production behavior.",
        "Language Agents that use Tools, Knowledge, structured output, or multi-round capability calls.",
    ),
    capabilities=(
        "Single-pass and multi-round conversational language Model execution.",
        "Parallel Tool calls within one capability round when the Model supports Tool calling.",
        "Durable Tool-boundary recovery without replaying completed Tool side effects.",
        "Structured output validation and JSON repair for compatible text output.",
    ),
    limitations=(
        "Requires a conversational language.generate Model with text output.",
        "Does not execute embedding, image, audio, video, JEV or other non-language operations.",
        "Does not add an explicit planning or reflection phase beyond model-directed capability use.",
    ),
    compatibility=_STANDARD_COMPATIBILITY,
    is_default=True,
)


def build_execution_strategy_registry() -> ExecutionStrategyRegistry:
    """Build the deterministic Execution Strategy catalog supported by this process."""

    registry = ExecutionStrategyRegistry()
    registry.register(_STANDARD_DESCRIPTOR)

    default = registry.current_default()
    if default.name != DEFAULT_EXECUTION_STRATEGY:
        raise InvalidDefaultExecutionStrategyError(
            "Historical execution fallback must remain the registered 'standard' Strategy"
        )
    return registry


SUPPORTED_EXECUTION_STRATEGIES = frozenset(
    descriptor.name
    for descriptor in build_execution_strategy_registry().list_descriptors()
)


def list_execution_strategies() -> list[dict[str, object]]:
    """Return backend-owned metadata for every selectable Execution Strategy."""

    return [
        descriptor.as_dict()
        for descriptor in build_execution_strategy_registry().list_descriptors()
    ]
