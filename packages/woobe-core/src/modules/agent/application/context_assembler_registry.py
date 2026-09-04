from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass

from modules.agent.application.default_context_assembler import DefaultContextAssembler
from modules.agent.application.interfaces.context_assembler import (
    DEFAULT_CONTEXT_ASSEMBLER_KEY,
    ContextAssembler,
    ContextAssemblerKey,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
    context_assembler_key_from_runtime_config,
)
from shared.contracts.errors import ValidationError


ContextAssemblerFactory = Callable[[], ContextAssembler]


@dataclass(frozen=True, slots=True)
class ContextAssemblerDescriptor:
    """Backend-owned product metadata required for every registered Context Manager."""

    key: ContextAssemblerKey
    display_name: str
    description: str
    behavior: str
    recommended_for: tuple[str, ...]
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...]
    configuration: str
    is_default: bool = False

    def __post_init__(self) -> None:
        required_text = {
            "display_name": self.display_name,
            "description": self.description,
            "behavior": self.behavior,
            "configuration": self.configuration,
        }
        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(f"Context assembler descriptor {field_name} must not be empty")

        required_lists = {
            "recommended_for": self.recommended_for,
            "capabilities": self.capabilities,
            "limitations": self.limitations,
        }
        for field_name, values in required_lists.items():
            if not values or any(not item.strip() for item in values):
                raise ValueError(
                    f"Context assembler descriptor {field_name} must contain non-empty values"
                )

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.key.name,
            "version": self.key.version,
            "display_name": self.display_name,
            "description": self.description,
            "behavior": self.behavior,
            "recommended_for": list(self.recommended_for),
            "capabilities": list(self.capabilities),
            "limitations": list(self.limitations),
            "configuration": self.configuration,
            "is_default": self.is_default,
        }


class ContextAssemblerRegistryError(ValueError):
    """Base error for deterministic ContextAssembler catalog failures."""


class DuplicateContextAssemblerError(ContextAssemblerRegistryError):
    pass


class UnknownContextAssemblerError(ContextAssemblerRegistryError):
    pass


class InvalidContextAssemblerFactoryError(TypeError):
    pass


class ContextAssemblerRegistry:
    """Explicit in-process catalog of versioned ContextAssembler factories."""

    __slots__ = ("_entries",)

    def __init__(self) -> None:
        self._entries: dict[
            ContextAssemblerKey,
            tuple[ContextAssemblerFactory, ContextAssemblerDescriptor],
        ] = {}

    def register(
        self,
        key: ContextAssemblerKey,
        factory: ContextAssemblerFactory,
        *,
        descriptor: ContextAssemblerDescriptor,
    ) -> None:
        if key in self._entries:
            raise DuplicateContextAssemblerError(
                f"Context assembler already registered: {key}"
            )
        if descriptor.key != key:
            raise ValueError("Context assembler descriptor key must match registration key")
        self._entries[key] = (factory, descriptor)

    def contains(self, key: ContextAssemblerKey) -> bool:
        return key in self._entries

    def create(self, key: ContextAssemblerKey) -> ContextAssembler:
        entry = self._entries.get(key)
        if entry is None:
            raise UnknownContextAssemblerError(f"Unknown context assembler: {key}")

        assembler = entry[0]()
        if not isinstance(assembler, ContextAssembler):
            raise InvalidContextAssemblerFactoryError(
                f"Context assembler factory for {key} returned an incompatible object"
            )
        return assembler

    def list_descriptors(self) -> tuple[ContextAssemblerDescriptor, ...]:
        return tuple(
            self._entries[key][1]
            for key in sorted(self._entries, key=lambda item: (item.name, item.version))
        )


_DEFAULT_DESCRIPTOR = ContextAssemblerDescriptor(
    key=DEFAULT_CONTEXT_ASSEMBLER_KEY,
    display_name="Standard Context Manager",
    description=(
        "Balanced deterministic context management for general-purpose Agent execution."
    ),
    behavior=(
        "Builds each Model Invocation context deterministically from the Agent's available "
        "context sources, applying Context Policy v1 budgets, priorities, pressure handling, "
        "ordering, deduplication, and provenance capture."
    ),
    recommended_for=(
        "General-purpose Agents that need predictable context behavior.",
        "Production workloads where replayability and stable snapshot behavior matter.",
    ),
    capabilities=(
        "Preserves mandatory system instructions and the current user input.",
        "Balances session history, knowledge, tool, artifact, delegation, and runtime context within configured budgets.",
        "Applies pressure trimming, ordering, and deduplication before each Model Invocation.",
        "Records source contributions and provenance in the Context Snapshot.",
    ),
    limitations=(
        "Does not perform autonomous context planning or iterative retrieval.",
        "Behavior is bounded by Context Policy v1 and the context sources available to the Agent.",
    ),
    configuration="Context Policy v1",
    is_default=True,
)


def build_context_assembler_registry() -> ContextAssemblerRegistry:
    """Build the deterministic catalog supported by this Woobe process."""

    registry = ContextAssemblerRegistry()
    registry.register(
        DEFAULT_CONTEXT_ASSEMBLER_KEY,
        DefaultContextAssembler,
        descriptor=_DEFAULT_DESCRIPTOR,
    )
    return registry


def build_context_assembler(key: ContextAssemblerKey) -> ContextAssembler:
    """Resolve one exact implementation from the supported catalog."""

    return build_context_assembler_registry().create(key)


class RegistryContextAssembler:
    """Concurrency-safe dispatcher that resolves selection from each Run snapshot."""

    __slots__ = ("_registry",)

    def __init__(self, registry: ContextAssemblerRegistry) -> None:
        self._registry = registry

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        name = request.runtime_context.context_assembler_name
        version = request.runtime_context.context_assembler_version
        key = (
            ContextAssemblerKey(name=name, version=version)
            if name and version
            else DEFAULT_CONTEXT_ASSEMBLER_KEY
        )
        return self._registry.create(key).assemble(request)


def build_runtime_context_assembler() -> ContextAssembler:
    """Build the runtime dispatcher without exposing the registry to execution code."""

    return RegistryContextAssembler(build_context_assembler_registry())


def validate_context_assembler_runtime_config(value: object) -> ContextAssemblerKey:
    try:
        key = context_assembler_key_from_runtime_config(value)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    if not build_context_assembler_registry().contains(key):
        raise ValidationError(f"Unsupported context assembler: {key}")
    return key


def canonicalize_context_assembler_runtime_config(value: object) -> dict:
    if value is not None and not isinstance(value, dict):
        raise ValidationError("Agent runtime_config must be an object")
    runtime_config = deepcopy(value) if isinstance(value, dict) else {}
    key = validate_context_assembler_runtime_config(runtime_config)
    runtime_config["context_assembler"] = key.as_dict()
    return runtime_config


def list_context_assemblers() -> list[dict[str, object]]:
    return [
        descriptor.as_dict()
        for descriptor in build_context_assembler_registry().list_descriptors()
    ]
