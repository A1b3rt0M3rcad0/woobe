from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace

from modules.agent.application.interfaces.context_assembler import (
    DEFAULT_CONTEXT_MANAGER,
    ContextAssemblerSelection,
    context_assembler_selection_from_runtime_config,
    normalize_context_manager_name,
)
from shared.contracts.errors import ValidationError


DEFAULT_CONTEXT_MANAGER_SETTING = DEFAULT_CONTEXT_MANAGER


@dataclass(frozen=True, slots=True)
class ContextAssemblerDescriptor:
    """Backend-owned product contract for one selectable Context Manager."""

    name: str
    display_name: str
    description: str
    behavior: str
    recommended_for: tuple[str, ...]
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...]
    configuration: str
    supports_skills: bool = False
    is_default: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", normalize_context_manager_name(self.name))
        required_text = {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "behavior": self.behavior,
            "configuration": self.configuration,
        }
        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"Context Manager descriptor {field_name} must not be empty"
                )

        required_lists = {
            "recommended_for": self.recommended_for,
            "capabilities": self.capabilities,
            "limitations": self.limitations,
        }
        for field_name, values in required_lists.items():
            if not values or any(not item.strip() for item in values):
                raise ValueError(
                    f"Context Manager descriptor {field_name} must contain non-empty values"
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
            "configuration": self.configuration,
            "supports_skills": self.supports_skills,
            "is_default": self.is_default,
        }


class ContextAssemblerRegistryError(ValueError):
    pass


class DuplicateContextAssemblerError(ContextAssemblerRegistryError):
    pass


class UnknownContextAssemblerError(ContextAssemblerRegistryError):
    pass


class InvalidDefaultContextManagerError(ContextAssemblerRegistryError):
    pass


class ContextAssemblerRegistry:
    """Backend-owned product catalog; runtime factories live in infrastructure."""

    __slots__ = ("_descriptors",)

    def __init__(self) -> None:
        self._descriptors: dict[str, ContextAssemblerDescriptor] = {}

    def register(self, descriptor: ContextAssemblerDescriptor) -> None:
        if descriptor.name in self._descriptors:
            raise DuplicateContextAssemblerError(
                f"Context Manager already registered: {descriptor.name}"
            )
        self._descriptors[descriptor.name] = descriptor

    def contains(self, name: str) -> bool:
        return normalize_context_manager_name(name) in self._descriptors

    def get(self, name: str) -> ContextAssemblerDescriptor:
        normalized = normalize_context_manager_name(name)
        descriptor = self._descriptors.get(normalized)
        if descriptor is None:
            raise UnknownContextAssemblerError(
                f"Unknown Context Manager: {normalized}"
            )
        return descriptor

    def current_default(self) -> ContextAssemblerDescriptor:
        defaults = [
            descriptor
            for descriptor in self._descriptors.values()
            if descriptor.is_default
        ]
        if len(defaults) != 1:
            raise InvalidDefaultContextManagerError(
                "Context Manager registry must contain exactly one default"
            )
        return defaults[0]

    def list_descriptors(self) -> tuple[ContextAssemblerDescriptor, ...]:
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


_STANDARD_DESCRIPTOR = ContextAssemblerDescriptor(
    name=DEFAULT_CONTEXT_MANAGER,
    display_name="Standard Context Manager",
    description=(
        "Balanced deterministic context management for general-purpose Agent execution."
    ),
    behavior=(
        "Builds each Model Invocation context deterministically from available context "
        "sources, applying Context Policy budgets, priorities, ordering, "
        "deduplication, provenance capture, and Run-local Skills materialization."
    ),
    recommended_for=(
        "General-purpose Agents that need predictable context behavior.",
        "Production workloads where stable context assembly and provenance matter.",
    ),
    capabilities=(
        "Preserves mandatory system instructions and the current user input.",
        "Balances session history, knowledge, tool, artifact, delegation, and runtime context within configured budgets.",
        "Reduces non-mandatory context deterministically when the effective input budget is exceeded.",
        "Classifies LOW/MODERATE/HIGH/CRITICAL context pressure for invocation evidence.",
        "Applies ordering and deduplication before each Model Invocation.",
        "Loads Skills on demand with per-Run retention and exact package provenance.",
        "Records source contributions and provenance in the Context Snapshot.",
    ),
    limitations=(
        "Does not perform semantic summarization or autonomous long-horizon compaction.",
        "Behavior is bounded by Context Policy and the context sources available to the Agent.",
    ),
    configuration="Context Policy",
    supports_skills=True,
)


def _configured_default_name(value: str) -> str:
    return normalize_context_manager_name(value.split(":", 1)[0])


def build_context_assembler_registry(
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
) -> ContextAssemblerRegistry:
    """Build product metadata without importing concrete infrastructure Managers."""

    default_name = _configured_default_name(default_context_manager)
    registry = ContextAssemblerRegistry()
    registry.register(
        replace(
            _STANDARD_DESCRIPTOR,
            is_default=_STANDARD_DESCRIPTOR.name == default_name,
        )
    )
    default = registry.current_default()
    if default.name != default_name:
        raise InvalidDefaultContextManagerError(
            f"Configured default Context Manager is not registered: {default_name}"
        )
    return registry


SUPPORTED_CONTEXT_MANAGERS = frozenset(
    descriptor.name
    for descriptor in build_context_assembler_registry().list_descriptors()
)


def validate_context_assembler_runtime_config(
    value: object,
    *,
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
    use_current_default_if_missing: bool = False,
) -> ContextAssemblerSelection:
    registry = build_context_assembler_registry(default_context_manager)

    has_selection = (
        isinstance(value, dict)
        and value.get("context_assembler") is not None
    )
    if use_current_default_if_missing and not has_selection:
        return ContextAssemblerSelection(registry.current_default().name)

    try:
        selection = context_assembler_selection_from_runtime_config(value)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    if not registry.contains(selection.name):
        raise ValidationError(f"Unsupported Context Manager: {selection.name}")
    return selection


def canonicalize_context_assembler_runtime_config(
    value: object,
    *,
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
    use_current_default_if_missing: bool = False,
) -> dict:
    if value is not None and not isinstance(value, dict):
        raise ValidationError("Agent runtime_config must be an object")

    runtime_config = deepcopy(value) if isinstance(value, dict) else {}
    selection = validate_context_assembler_runtime_config(
        runtime_config,
        default_context_manager=default_context_manager,
        use_current_default_if_missing=use_current_default_if_missing,
    )
    runtime_config["context_assembler"] = selection.as_dict()
    return runtime_config


def list_context_assemblers(
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
) -> list[dict[str, object]]:
    return [
        descriptor.as_dict()
        for descriptor in build_context_assembler_registry(
            default_context_manager
        ).list_descriptors()
    ]


__all__ = [
    "DEFAULT_CONTEXT_MANAGER_SETTING",
    "SUPPORTED_CONTEXT_MANAGERS",
    "ContextAssemblerDescriptor",
    "ContextAssemblerRegistry",
    "InvalidDefaultContextManagerError",
    "UnknownContextAssemblerError",
    "build_context_assembler_registry",
    "canonicalize_context_assembler_runtime_config",
    "list_context_assemblers",
    "validate_context_assembler_runtime_config",
]
