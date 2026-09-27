from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace

from modules.agent.application.context_managers.standard import StandardContextManager
from modules.agent.application.context_managers.standard_skills import StandardSkillsContextManager
from modules.agent.application.interfaces.context_manager import (
    STANDARD_CONTEXT_MANAGER_KEY,
    ContextManager,
    ContextManagerKey,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
    ContextCompactionOutput,
    ContextCompactionRequest,
    ContextInspectionOutput,
    ContextInspectionRequest,
    ContextManagerCapabilities,
    context_manager_key_from_runtime_config,
)
from shared.contracts.errors import ValidationError


DEFAULT_CONTEXT_MANAGER_SETTING = "stdcm"
ContextManagerFactory = Callable[[], ContextManager]


@dataclass(frozen=True, slots=True)
class ContextManagerDescriptor:
    """Backend-owned product metadata for one registered Context Manager."""

    key: ContextManagerKey
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
                    f"Context manager descriptor {field_name} must not be empty"
                )

        required_lists = {
            "recommended_for": self.recommended_for,
            "capabilities": self.capabilities,
            "limitations": self.limitations,
        }
        for field_name, values in required_lists.items():
            if not values or any(not item.strip() for item in values):
                raise ValueError(
                    f"Context manager descriptor {field_name} must contain non-empty values"
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


class ContextManagerRegistryError(ValueError):
    """Base error for deterministic Context Manager catalog failures."""


class DuplicateContextManagerError(ContextManagerRegistryError):
    pass


class UnknownContextManagerError(ContextManagerRegistryError):
    pass


class InvalidContextManagerFactoryError(TypeError):
    pass


class InvalidDefaultContextManagerError(ContextManagerRegistryError):
    pass


class ContextManagerRegistry:
    """Explicit in-process catalog keyed only by Context Manager name."""

    __slots__ = ("_entries", "_default_key")

    def __init__(self) -> None:
        self._entries: dict[
            ContextManagerKey,
            tuple[ContextManagerFactory, ContextManagerDescriptor],
        ] = {}
        self._default_key: ContextManagerKey | None = None

    def register(
        self,
        key: ContextManagerKey,
        factory: ContextManagerFactory,
        *,
        descriptor: ContextManagerDescriptor,
    ) -> None:
        if key in self._entries:
            raise DuplicateContextManagerError(
                f"Context manager already registered: {key}"
            )
        if descriptor.key != key:
            raise ValueError(
                "Context Manager descriptor key must match registration key"
            )
        self._entries[key] = (factory, descriptor)

    def set_default(self, key: ContextManagerKey) -> None:
        if key not in self._entries:
            raise InvalidDefaultContextManagerError(
                f"Configured default Context Manager is not registered: {key}"
            )
        self._default_key = key

    def contains(self, key: ContextManagerKey) -> bool:
        return key in self._entries

    def current_default(self) -> ContextManagerDescriptor:
        if self._default_key is None:
            raise InvalidDefaultContextManagerError(
                "Context manager registry has no system default"
            )
        descriptor = self._entries[self._default_key][1]
        return replace(descriptor, is_default=True)

    def create(self, key: ContextManagerKey) -> ContextManager:
        entry = self._entries.get(key)
        if entry is None:
            raise UnknownContextManagerError(f"Unknown context manager: {key}")

        manager = entry[0]()
        if not isinstance(manager, ContextManager):
            raise InvalidContextManagerFactoryError(
                f"Context manager factory for {key} returned an incompatible object"
            )
        return manager

    def list_descriptors(self) -> tuple[ContextManagerDescriptor, ...]:
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


_STANDARD_DESCRIPTOR = ContextManagerDescriptor(
    key=STANDARD_CONTEXT_MANAGER_KEY,
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


def _configured_default_manager(value: str) -> ContextManagerKey:
    try:
        return ContextManagerKey.parse(value)
    except ValueError as exc:
        raise InvalidDefaultContextManagerError(
            "WOOBE_DEFAULT_CONTEXT_MANAGER must be a registered Context Manager name"
        ) from exc


def _register_builtin_context_managers(
    registry: ContextManagerRegistry,
) -> None:
    """Register built-in managers. Different behavior uses different names."""

    registry.register(
        STANDARD_CONTEXT_MANAGER_KEY,
        lambda: StandardSkillsContextManager(StandardContextManager()),
        descriptor=_STANDARD_DESCRIPTOR,
    )


def build_context_manager_registry(
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
) -> ContextManagerRegistry:
    registry = ContextManagerRegistry()
    _register_builtin_context_managers(registry)
    registry.set_default(_configured_default_manager(default_context_manager))
    return registry


def build_context_manager(
    key: ContextManagerKey,
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
) -> ContextManager:
    return build_context_manager_registry(default_context_manager).create(key)


class RegistryContextManager:
    """Concurrency-safe dispatcher for the Context Manager selected by name."""

    __slots__ = ("_registry",)

    def __init__(self, registry: ContextManagerRegistry) -> None:
        self._registry = registry

    def _resolve(self, environment) -> ContextManager:
        name = getattr(environment, "context_manager_name", None)
        key = (
            ContextManagerKey(name=name)
            if isinstance(name, str) and name.strip()
            else self._registry.current_default().key
        )
        return self._registry.create(key)

    def inspect(
        self,
        request: ContextInspectionRequest,
    ) -> ContextInspectionOutput:
        return self._resolve(request.environment).inspect(request)

    async def compact(
        self,
        request: ContextCompactionRequest,
        capabilities: ContextManagerCapabilities,
    ) -> ContextCompactionOutput:
        return await self._resolve(request.environment).compact(
            request,
            capabilities,
        )

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        return self._resolve(request.environment).assemble(request)


def build_runtime_context_manager(
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
) -> ContextManager:
    return RegistryContextManager(
        build_context_manager_registry(default_context_manager)
    )


def _has_context_manager_selection(value: object) -> bool:
    return isinstance(value, dict) and (
        isinstance(value.get("context_manager"), dict)
        or isinstance(value.get("context_assembler"), dict)
    )


def validate_context_manager_runtime_config(
    value: object,
    *,
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
    use_current_default_if_missing: bool = False,
) -> ContextManagerKey:
    registry = build_context_manager_registry(default_context_manager)

    if use_current_default_if_missing and not _has_context_manager_selection(value):
        return registry.current_default().key

    try:
        key = context_manager_key_from_runtime_config(value)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    if not registry.contains(key):
        raise ValidationError(f"Unsupported context manager: {key}")
    return key


def canonicalize_context_manager_runtime_config(
    value: object,
    *,
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
    use_current_default_if_missing: bool = False,
) -> dict:
    if value is not None and not isinstance(value, dict):
        raise ValidationError("Agent runtime_config must be an object")
    runtime_config = deepcopy(value) if isinstance(value, dict) else {}
    key = validate_context_manager_runtime_config(
        runtime_config,
        default_context_manager=default_context_manager,
        use_current_default_if_missing=use_current_default_if_missing,
    )
    runtime_config.pop("context_assembler", None)
    runtime_config["context_manager"] = key.as_dict()
    return runtime_config


def list_context_managers(
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER_SETTING,
) -> list[dict[str, object]]:
    return [
        descriptor.as_dict()
        for descriptor in build_context_manager_registry(
            default_context_manager
        ).list_descriptors()
    ]
