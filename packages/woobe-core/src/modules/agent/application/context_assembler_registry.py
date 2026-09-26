from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace

from modules.agent.application.context_managers.standard import StandardContextAssembler
from modules.agent.application.context_managers.standard_v2 import StandardSkillsContextAssembler
from modules.agent.application.interfaces.context_assembler import (
    LEGACY_DEFAULT_CONTEXT_ASSEMBLER_KEY,
    STANDARD_CONTEXT_ASSEMBLER_KEY,
    ContextAssembler,
    ContextAssemblerKey,
    ContextAssemblerSelection,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
    ContextCompactionOutput,
    ContextCompactionRequest,
    ContextInspectionOutput,
    ContextInspectionRequest,
    ContextManagerCapabilities,
    context_assembler_selection_from_runtime_config,
)
from shared.contracts.errors import ValidationError


DEFAULT_CONTEXT_MANAGER_SETTING = "stdcm:v1"
ContextAssemblerFactory = Callable[[], ContextAssembler]


@dataclass(frozen=True, slots=True)
class ContextAssemblerDescriptor:
    """Backend-owned product metadata required for every registered Context Manager."""

    key: ContextAssemblerKey
    strategy_key: ContextAssemblerKey
    display_name: str
    description: str
    behavior: str
    recommended_for: tuple[str, ...]
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...]
    configuration: str
    supports_skills: bool = False
    is_default: bool = False
    is_system_default_alias: bool = False

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

        if self.is_default and not self.is_system_default_alias:
            raise ValueError("Only a system default alias may be marked as default")

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.key.name,
            "version": self.key.version,
            "strategy_name": self.strategy_key.name,
            "strategy_version": self.strategy_key.version,
            "display_name": self.display_name,
            "description": self.description,
            "behavior": self.behavior,
            "recommended_for": list(self.recommended_for),
            "capabilities": list(self.capabilities),
            "limitations": list(self.limitations),
            "configuration": self.configuration,
            "supports_skills": self.supports_skills,
            "is_default": self.is_default,
            "is_system_default_alias": self.is_system_default_alias,
        }


class ContextAssemblerRegistryError(ValueError):
    """Base error for deterministic ContextAssembler catalog failures."""


class DuplicateContextAssemblerError(ContextAssemblerRegistryError):
    pass


class UnknownContextAssemblerError(ContextAssemblerRegistryError):
    pass


class InvalidContextAssemblerFactoryError(TypeError):
    pass


class InvalidDefaultContextManagerError(ContextAssemblerRegistryError):
    pass


class ContextAssemblerRegistry:
    """Explicit in-process catalog of strategies plus one system-default alias."""

    __slots__ = ("_entries", "_current_default_key")

    def __init__(self) -> None:
        self._entries: dict[
            ContextAssemblerKey,
            tuple[ContextAssemblerFactory, ContextAssemblerDescriptor],
        ] = {}
        self._current_default_key: ContextAssemblerKey | None = None

    def register(
        self,
        key: ContextAssemblerKey,
        factory: ContextAssemblerFactory,
        *,
        descriptor: ContextAssemblerDescriptor,
    ) -> None:
        """Register one explicit strategy identity."""

        if key.name == "default":
            raise ValueError(
                "The 'default' Context Manager identity is reserved for the system-default alias"
            )
        if key in self._entries:
            raise DuplicateContextAssemblerError(
                f"Context assembler already registered: {key}"
            )
        if descriptor.key != key or descriptor.strategy_key != key:
            raise ValueError(
                "Explicit Context Manager descriptor key and strategy_key must match registration key"
            )
        if descriptor.is_default or descriptor.is_system_default_alias:
            raise ValueError("Explicit strategy registrations cannot be system-default aliases")
        self._entries[key] = (factory, descriptor)

    def register_default_alias(
        self,
        *,
        strategy_key: ContextAssemblerKey,
    ) -> ContextAssemblerKey:
        """Expose the configured strategy through the reserved ``default`` identity.

        The alias version mirrors the configured strategy version. New Agent snapshots
        additionally freeze ``strategy_name``/``strategy_version``, so changing the
        system default later cannot alter existing Agent or Release behavior.
        """

        target = self._entries.get(strategy_key)
        if target is None:
            raise InvalidDefaultContextManagerError(
                f"Configured default Context Manager is not registered: {strategy_key}"
            )
        if self._current_default_key is not None:
            raise InvalidDefaultContextManagerError(
                f"System default Context Manager already registered: {self._current_default_key}"
            )

        alias_key = ContextAssemblerKey(name="default", version=strategy_key.version)
        if alias_key in self._entries:
            raise DuplicateContextAssemblerError(
                f"Context assembler already registered: {alias_key}"
            )

        factory, strategy_descriptor = target
        alias_descriptor = replace(
            strategy_descriptor,
            key=alias_key,
            strategy_key=strategy_key,
            is_default=True,
            is_system_default_alias=True,
        )
        self._entries[alias_key] = (factory, alias_descriptor)
        self._current_default_key = alias_key
        return alias_key

    def contains(self, key: ContextAssemblerKey) -> bool:
        return key in self._entries

    def contains_strategy(self, key: ContextAssemblerKey) -> bool:
        entry = self._entries.get(key)
        return bool(entry and not entry[1].is_system_default_alias)

    def current_default(self) -> ContextAssemblerDescriptor:
        if self._current_default_key is None:
            raise InvalidDefaultContextManagerError(
                "Context assembler registry has no system default"
            )
        return self._entries[self._current_default_key][1]

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

    def create_strategy(self, strategy_key: ContextAssemblerKey) -> ContextAssembler:
        if not self.contains_strategy(strategy_key):
            raise UnknownContextAssemblerError(
                f"Unknown context assembler strategy: {strategy_key}"
            )
        return self.create(strategy_key)

    def list_descriptors(self) -> tuple[ContextAssemblerDescriptor, ...]:
        return tuple(
            self._entries[key][1]
            for key in sorted(
                self._entries,
                key=lambda item: (
                    0 if self._entries[item][1].is_default else 1,
                    item.name,
                    item.version,
                ),
            )
        )


_STANDARD_DESCRIPTOR = ContextAssemblerDescriptor(
    key=STANDARD_CONTEXT_ASSEMBLER_KEY,
    strategy_key=STANDARD_CONTEXT_ASSEMBLER_KEY,
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
)


def _configured_default_strategy(value: str) -> ContextAssemblerKey:
    try:
        key = ContextAssemblerKey.parse(value)
    except ValueError as exc:
        raise InvalidDefaultContextManagerError(
            "WOOBE_DEFAULT_CONTEXT_MANAGER must use '<strategy>:<version>'"
        ) from exc
    if key.name == "default":
        raise InvalidDefaultContextManagerError(
            "WOOBE_DEFAULT_CONTEXT_MANAGER must identify a concrete strategy, not the default alias"
        )
    return key


def _register_builtin_context_manager_strategies(
    registry: ContextAssemblerRegistry,
) -> None:
    """Single explicit extension point for built-in Context Manager strategies.

    Concrete implementations live under ``application/context_managers``. Add a
    stable versioned strategy and its backend-owned descriptor here; Runtime code
    must not import the concrete implementation directly.
    """

    skills_key = ContextAssemblerKey(name="stdcm", version="v2")
    registry.register(
        skills_key, lambda: StandardSkillsContextAssembler(StandardContextAssembler()),
        descriptor=replace(
            _STANDARD_DESCRIPTOR, key=skills_key, strategy_key=skills_key,
            display_name="Standard Context Manager v2", supports_skills=True,
            description="Deterministic context management with versioned Skills loaded on demand.",
            behavior="Loads compact Skill discovery metadata and protects activated instructions and resources until the Agent Run ends. Preserves v1 source handling for other context.",
            capabilities=(*_STANDARD_DESCRIPTOR.capabilities, "Loads Skills on demand with per-Run retention, bounded discovery, and exact package provenance."),
            limitations=("Skills support text instructions and resources; arbitrary scripts are not executed.", "Activated instructions cannot be compacted; an insufficient budget blocks the invocation."),
            configuration="Context Policy v1 with Skills budgets",
        ),
    )
    registry.register(
        STANDARD_CONTEXT_ASSEMBLER_KEY,
        StandardContextAssembler,
        descriptor=_STANDARD_DESCRIPTOR,
    )


def build_context_assembler_registry(
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
) -> ContextAssemblerRegistry:
    """Build the deterministic catalog supported by this Woobe process."""

    registry = ContextAssemblerRegistry()
    _register_builtin_context_manager_strategies(registry)
    registry.register_default_alias(
        strategy_key=_configured_default_strategy(default_context_manager),
    )
    return registry


def build_context_assembler(
    key: ContextAssemblerKey,
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
) -> ContextAssembler:
    """Resolve one exact selectable identity from the supported catalog."""

    return build_context_assembler_registry(default_context_manager).create(key)


class RegistryContextAssembler:
    """Concurrency-safe dispatcher for the frozen Context Manager strategy."""

    __slots__ = ("_registry",)

    def __init__(self, registry: ContextAssemblerRegistry) -> None:
        self._registry = registry

    def _resolve(self, runtime_context) -> ContextAssembler:
        strategy_name = getattr(
            runtime_context,
            "context_assembler_strategy_name",
            None,
        )
        strategy_version = getattr(
            runtime_context,
            "context_assembler_strategy_version",
            None,
        )
        if strategy_name and strategy_version:
            strategy_key = ContextAssemblerKey(
                name=strategy_name,
                version=strategy_version,
            )
        else:
            name = getattr(runtime_context, "context_assembler_name", None)
            version = getattr(runtime_context, "context_assembler_version", None)
            selection_key = (
                ContextAssemblerKey(name=name, version=version)
                if name and version
                else LEGACY_DEFAULT_CONTEXT_ASSEMBLER_KEY
            )
            strategy_key = (
                STANDARD_CONTEXT_ASSEMBLER_KEY
                if selection_key == LEGACY_DEFAULT_CONTEXT_ASSEMBLER_KEY
                else selection_key
            )
        return self._registry.create_strategy(strategy_key)

    def inspect(
        self,
        request: ContextInspectionRequest,
    ) -> ContextInspectionOutput:
        return self._resolve(request.runtime_context).inspect(request)

    async def compact(
        self,
        request: ContextCompactionRequest,
        capabilities: ContextManagerCapabilities,
    ) -> ContextCompactionOutput:
        return await self._resolve(request.runtime_context).compact(
            request,
            capabilities,
        )

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        return self._resolve(request.runtime_context).assemble(request)


def build_runtime_context_assembler(
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
) -> ContextAssembler:
    """Build the runtime dispatcher without exposing the registry to execution code."""

    return RegistryContextAssembler(
        build_context_assembler_registry(default_context_manager)
    )


def _has_context_assembler_selection(value: object) -> bool:
    return isinstance(value, dict) and isinstance(value.get("context_assembler"), dict)


def validate_context_assembler_runtime_config(
    value: object,
    *,
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
    use_current_default_if_missing: bool = False,
) -> ContextAssemblerSelection:
    registry = build_context_assembler_registry(default_context_manager)

    if use_current_default_if_missing and not _has_context_assembler_selection(value):
        descriptor = registry.current_default()
        return ContextAssemblerSelection(
            selection_key=descriptor.key,
            strategy_key=descriptor.strategy_key,
        )

    try:
        selection = context_assembler_selection_from_runtime_config(value)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    if not registry.contains_strategy(selection.strategy_key):
        raise ValidationError(
            f"Unsupported context assembler strategy: {selection.strategy_key}"
        )

    if selection.selection_key.name == "default":
        if selection.selection_key.version != selection.strategy_key.version:
            raise ValidationError(
                "System default Context Manager selection version must match the frozen strategy version"
            )
    else:
        if selection.selection_key != selection.strategy_key:
            raise ValidationError(
                "Explicit Context Manager selection must match the resolved strategy"
            )
        if not registry.contains(selection.selection_key):
            raise ValidationError(
                f"Unsupported context assembler: {selection.selection_key}"
            )

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
