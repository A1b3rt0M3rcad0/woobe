from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from modules.agent.application.default_context_assembler import DefaultContextAssembler
from modules.agent.application.interfaces.context_assembler import ContextAssembler


ContextAssemblerFactory = Callable[[], ContextAssembler]


@dataclass(frozen=True, slots=True)
class ContextAssemblerKey:
    """Stable identity for a ContextAssembler implementation.

    Name and version are intentionally separate so future Agent Release snapshots can
    persist an exact implementation identity without coupling runtime execution to a
    concrete class.
    """

    name: str
    version: str

    def __post_init__(self) -> None:
        name = self.name.strip()
        version = self.version.strip()
        if not name:
            raise ValueError("Context assembler name must not be empty")
        if not version:
            raise ValueError("Context assembler version must not be empty")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "version", version)

    def __str__(self) -> str:
        return f"{self.name}:{self.version}"


class ContextAssemblerRegistryError(ValueError):
    """Base error for deterministic ContextAssembler resolution failures."""


class DuplicateContextAssemblerError(ContextAssemblerRegistryError):
    pass


class UnknownContextAssemblerError(ContextAssemblerRegistryError):
    pass


class InvalidContextAssemblerFactoryError(TypeError):
    pass


class ContextAssemblerRegistry:
    """Explicit in-process catalog of versioned ContextAssembler factories.

    The registry is a composition concern. Agent Runtime receives the resolved
    ContextAssembler and never depends on this registry directly.
    """

    __slots__ = ("_factories",)

    def __init__(self) -> None:
        self._factories: dict[ContextAssemblerKey, ContextAssemblerFactory] = {}

    def register(
        self,
        key: ContextAssemblerKey,
        factory: ContextAssemblerFactory,
    ) -> None:
        if key in self._factories:
            raise DuplicateContextAssemblerError(
                f"Context assembler already registered: {key}"
            )
        self._factories[key] = factory

    def create(self, key: ContextAssemblerKey) -> ContextAssembler:
        factory = self._factories.get(key)
        if factory is None:
            raise UnknownContextAssemblerError(f"Unknown context assembler: {key}")

        assembler = factory()
        if not isinstance(assembler, ContextAssembler):
            raise InvalidContextAssemblerFactoryError(
                f"Context assembler factory for {key} returned an incompatible object"
            )
        return assembler


DEFAULT_CONTEXT_ASSEMBLER_KEY = ContextAssemblerKey(name="default", version="v1")


def build_context_assembler_registry() -> ContextAssemblerRegistry:
    """Build the deterministic catalog supported by this Woobe process."""

    registry = ContextAssemblerRegistry()
    registry.register(DEFAULT_CONTEXT_ASSEMBLER_KEY, DefaultContextAssembler)
    return registry


def build_context_assembler(key: ContextAssemblerKey) -> ContextAssembler:
    """Resolve one assembler without exposing the registry to Agent Runtime."""

    return build_context_assembler_registry().create(key)
