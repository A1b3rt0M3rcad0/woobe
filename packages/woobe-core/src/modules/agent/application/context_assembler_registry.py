from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace

from modules.agent.application.context_managers.standard import StandardContextAssembler
from modules.agent.application.context_managers.standard_skills import StandardSkillsContextAssembler
from modules.agent.application.interfaces.context_assembler import (
    STANDARD_CONTEXT_ASSEMBLER_KEY,
    ContextAssembler,
    ContextAssemblerKey,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
    ContextCompactionOutput,
    ContextCompactionRequest,
    ContextInspectionOutput,
    ContextInspectionRequest,
    ContextManagerCapabilities,
    context_assembler_key_from_runtime_config,
)
from shared.contracts.errors import ValidationError


DEFAULT_CONTEXT_MANAGER_SETTING = "stdcm"
ContextAssemblerFactory = Callable[[], ContextAssembler]


@dataclass(frozen=True, slots=True)
class ContextAssemblerDescriptor:
    """Backend-owned product metadata for one registered Context Manager."""

    key: ContextAssemblerKey
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
        required_text = {
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
    """Base error for deterministic Context Manager catalog failures."""


class DuplicateContextAssemblerError(ContextAssemblerRegistryError):
    pass


class UnknownContextAssemblerError(ContextAssemblerRegistryError):
    pass


class InvalidContextAssemblerFactoryError(TypeError):
    pass


class InvalidDefaultContextManagerError(ContextAssemblerRegistryError):
    pass


class ContextAssemblerRegistry:
    """Explicit in-process catalog keyed only by Context Manager name."""

    __slots__ = ("_entries", "_default_key")

    def __init__(self) -> None:
        self._entries: dict[
            ContextAssemblerKey,
            tuple[ContextAssemblerFactory, ContextAssemblerDescriptor],
        ] = {}
        self._default_key: ContextAssemblerKey | None = None

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
            raise ValueError(
                "Context Manager descriptor key must match registration key"
            )
        self._entries[key] = (factory, descriptor)

    def set_default(self, key: ContextAssemblerKey) -> None:
        if key not in self._entries:
            raise InvalidDefaultContextManagerError(
                f"Configured default Context Manager is not registered: {key}"
            )
        self._default_key = key

    def contains(self, key: ContextAssemblerKey) -> bool:
        return key in self._entries

    def current_default(self) -> ContextAssemblerDescriptor:
        if self._default_key is None:
            raise InvalidDefaultContextManagerError(
                "Context assembler registry has no system default"
            )
        descriptor = self._entries[self._default_key][1]
        return replace(descriptor, is_default=True)

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
            replace(
                self._entries[key][1],
                is_default=key == self._default_key,
            )
            for key in sorted(
                self._entries,
                key=lambda item: (
                    0 if item == self._default_key else 1,
                    item.name,
                ),
            )
        )


_STANDARD_DESCRIPTOR = ContextAssemblerDescriptor(
    key=STANDARD_CONTEXT_ASSEMBLER_KEY,
    display_name="Standard Context Manager",
    description=(
        "Programmable pressure-aware context management for general-purpose Agent execution."
    ),
    behavior=(
        "Owns Context inspection, pressure-aware compaction, summarize-and-replace, "
        "Skills materialization, deterministic budgeting, ordering, deduplication, "
        "provenance and final materialization behind the Context Manager interface."
    ),
    recommended_for=(
        "General-purpose Agents that need programmable context behavior.",
        "Production workloads that need bounded context, Skills and deterministic assembly.",
    ),
    capabilities=(
        "Preserves mandatory system instructions and the current user input.",
        "Balances session history, knowledge, tools, skills, artifacts, delegation and runtime context.",
        "Compacts older Session context under pressure through manager-owned model-assisted summarization.",
        "Replaces covered Session messages with persisted summary contributions.",
        "Loads Skills on demand with per-Run retention and exact package provenance.",
        "Records source contributions and provenance in the Context Snapshot.",
    ),
    limitations=(
        "The built-in compaction strategy currently summarizes Session history only.",
        "Model-assisted compaction uses the Agent's bound primary Model capability.",
    ),
    configuration="Context Policy v1 plus Standard Context Manager defaults",
    supports_skills=True,
)


def _configured_default_manager(value: str) -> ContextAssemblerKey:
    try:
        return ContextAssemblerKey.parse(value)
    except ValueError as exc:
        raise InvalidDefaultContextManagerError(
            "WOOBE_DEFAULT_CONTEXT_MANAGER must be a registered Context Manager name"
        ) from exc


def _register_builtin_context_managers(
    registry: ContextAssemblerRegistry,
) -> None:
    """Register built-in managers. Different behavior uses different names."""

    registry.register(
        STANDARD_CONTEXT_ASSEMBLER_KEY,
        lambda: StandardSkillsContextAssembler(StandardContextAssembler()),
        descriptor=_STANDARD_DESCRIPTOR,
    )


def build_context_assembler_registry(
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
) -> ContextAssemblerRegistry:
    registry = ContextAssemblerRegistry()
    _register_builtin_context_managers(registry)
    registry.set_default(_configured_default_manager(default_context_manager))
    return registry


def build_context_assembler(
    key: ContextAssemblerKey,
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
) -> ContextAssembler:
    return build_context_assembler_registry(default_context_manager).create(key)


class RegistryContextAssembler:
    """Concurrency-safe dispatcher for the Context Manager selected by name."""

    __slots__ = ("_registry",)

    def __init__(self, registry: ContextAssemblerRegistry) -> None:
        self._registry = registry

    def _resolve(self, runtime_context) -> ContextAssembler:
        name = getattr(runtime_context, "context_assembler_name", None)
        key = (
            ContextAssemblerKey(name=name)
            if isinstance(name, str) and name.strip()
            else self._registry.current_default().key
        )
        return self._registry.create(key)

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
) -> ContextAssemblerKey:
    registry = build_context_assembler_registry(default_context_manager)

    if use_current_default_if_missing and not _has_context_assembler_selection(value):
        return registry.current_default().key

    try:
        key = context_assembler_key_from_runtime_config(value)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    if not registry.contains(key):
        raise ValidationError(f"Unsupported context assembler: {key}")
    return key


def canonicalize_context_assembler_runtime_config(
    value: object,
    *,
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
    use_current_default_if_missing: bool = False,
) -> dict:
    if value is not None and not isinstance(value, dict):
        raise ValidationError("Agent runtime_config must be an object")
    runtime_config = deepcopy(value) if isinstance(value, dict) else {}
    key = validate_context_assembler_runtime_config(
        runtime_config,
        default_context_manager=default_context_manager,
        use_current_default_if_missing=use_current_default_if_missing,
    )
    runtime_config["context_assembler"] = key.as_dict()
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
