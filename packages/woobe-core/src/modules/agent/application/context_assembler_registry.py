from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace

from modules.agent.application.context_managers.standard import StandardContextAssembler
from modules.agent.application.interfaces.context_assembler import (
    DEFAULT_CONTEXT_MANAGER,
    ContextAssembler,
    ContextAssemblerSelection,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
    context_assembler_selection_from_runtime_config,
    normalize_context_manager_name,
)
from shared.contracts.errors import ValidationError


DEFAULT_CONTEXT_MANAGER_SETTING = DEFAULT_CONTEXT_MANAGER
ContextAssemblerFactory = Callable[[], ContextAssembler]


@dataclass(frozen=True, slots=True)
class ContextAssemblerDescriptor:
    """Backend-owned product metadata for one selectable Context Manager."""

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
                    f"Context assembler descriptor {field_name} must not be empty"
                )
        for field_name, values in {
            "recommended_for": self.recommended_for,
            "capabilities": self.capabilities,
            "limitations": self.limitations,
        }.items():
            if not values or any(not item.strip() for item in values):
                raise ValueError(
                    f"Context assembler descriptor {field_name} must contain non-empty values"
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


class InvalidContextAssemblerFactoryError(TypeError):
    pass


class InvalidDefaultContextManagerError(ContextAssemblerRegistryError):
    pass


class ContextAssemblerRegistry:
    """Explicit in-process catalog of stable unversioned Context Managers."""

    __slots__ = ("_entries", "_default_name")

    def __init__(self, *, default_name: str) -> None:
        self._entries: dict[
            str,
            tuple[ContextAssemblerFactory, ContextAssemblerDescriptor],
        ] = {}
        self._default_name = normalize_context_manager_name(default_name)

    def register(
        self,
        name: str,
        factory: ContextAssemblerFactory,
        *,
        descriptor: ContextAssemblerDescriptor,
    ) -> None:
        normalized = normalize_context_manager_name(name)
        if normalized in self._entries:
            raise DuplicateContextAssemblerError(
                f"Context Manager already registered: {normalized}"
            )
        if descriptor.name != normalized:
            raise ValueError(
                "Context Manager descriptor name must match registration name"
            )
        self._entries[normalized] = (
            factory,
            replace(descriptor, is_default=normalized == self._default_name),
        )

    def contains(self, name: str) -> bool:
        return normalize_context_manager_name(name) in self._entries

    def current_default(self) -> ContextAssemblerDescriptor:
        entry = self._entries.get(self._default_name)
        if entry is None:
            raise InvalidDefaultContextManagerError(
                f"Configured default Context Manager is not registered: {self._default_name}"
            )
        return entry[1]

    def create(self, name: str) -> ContextAssembler:
        normalized = normalize_context_manager_name(name)
        entry = self._entries.get(normalized)
        if entry is None:
            raise UnknownContextAssemblerError(
                f"Unknown Context Manager: {normalized}"
            )
        assembler = entry[0]()
        if not isinstance(assembler, ContextAssembler):
            raise InvalidContextAssemblerFactoryError(
                f"Context Manager factory for {normalized} returned an incompatible object"
            )
        return assembler

    def list_descriptors(self) -> tuple[ContextAssemblerDescriptor, ...]:
        return tuple(
            sorted(
                (entry[1] for entry in self._entries.values()),
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
        "Builds each Model Invocation context deterministically from the Agent's available "
        "context sources, applies Context Policy budgets, priorities, pressure handling, "
        "ordering and provenance capture, and materializes Run-local Skills when enabled."
    ),
    recommended_for=(
        "General-purpose Agents that need predictable context behavior.",
        "Production workloads where stable context assembly and provenance matter.",
    ),
    capabilities=(
        "Preserves mandatory system instructions and the current user input.",
        "Balances session history, knowledge, tool, artifact, delegation, and runtime context within configured budgets.",
        "Applies pressure trimming, ordering, and deduplication before each Model Invocation.",
        "Loads Skills on demand with per-Run retention and exact package provenance.",
        "Records source contributions and provenance in the Context Snapshot.",
    ),
    limitations=(
        "Does not perform autonomous context planning or semantic long-horizon compaction.",
        "Behavior is bounded by Context Policy and the context sources available to the Agent.",
    ),
    configuration="Context Policy",
    supports_skills=True,
)


def _configured_default_strategy(value: str) -> str:
    raw_name = value.split(":", 1)[0]
    return normalize_context_manager_name(raw_name)


def _register_builtin_context_managers(registry: ContextAssemblerRegistry) -> None:
    registry.register(
        DEFAULT_CONTEXT_MANAGER,
        StandardContextAssembler,
        descriptor=_STANDARD_DESCRIPTOR,
    )


def build_context_assembler_registry(
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
) -> ContextAssemblerRegistry:
    registry = ContextAssemblerRegistry(
        default_name=_configured_default_strategy(default_context_manager)
    )
    _register_builtin_context_managers(registry)
    registry.current_default()
    return registry


def build_context_assembler(
    name: str,
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
) -> ContextAssembler:
    return build_context_assembler_registry(default_context_manager).create(name)


class RegistryContextAssembler:
    """Concurrency-safe dispatcher for the Manager frozen in each Agent snapshot."""

    __slots__ = ("_registry",)

    def __init__(self, registry: ContextAssemblerRegistry) -> None:
        self._registry = registry

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        raw_name = getattr(request.runtime_context, "context_assembler_name", None)
        return self._registry.create(
            normalize_context_manager_name(raw_name or DEFAULT_CONTEXT_MANAGER)
        ).assemble(request)


def build_runtime_context_assembler(
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
) -> ContextAssembler:
    return RegistryContextAssembler(
        build_context_assembler_registry(default_context_manager)
    )


def _has_context_assembler_selection(value: object) -> bool:
    return isinstance(value, dict) and value.get("context_assembler") is not None


def validate_context_assembler_runtime_config(
    value: object,
    *,
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
    use_current_default_if_missing: bool = False,
) -> ContextAssemblerSelection:
    registry = build_context_assembler_registry(default_context_manager)

    if use_current_default_if_missing and not _has_context_assembler_selection(value):
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
