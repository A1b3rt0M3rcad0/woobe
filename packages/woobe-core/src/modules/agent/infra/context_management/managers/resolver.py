from __future__ import annotations

from collections.abc import Callable

from modules.agent.application.interfaces.context_assembler import (
    DEFAULT_CONTEXT_MANAGER,
    ContextAssembler,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
    normalize_context_manager_name,
)
from modules.agent.application.interfaces.context_manager import ContextManager
from modules.agent.infra.context_management.manager_runtime import ContextManagerRunner
from modules.agent.infra.context_management.managers.standard import StandardContextManager


_BUILTIN_CONTEXT_MANAGER_FACTORIES: dict[
    str,
    Callable[[], ContextManager],
] = {
    StandardContextManager.name: StandardContextManager,
}


def builtin_context_manager_names() -> frozenset[str]:
    return frozenset(_BUILTIN_CONTEXT_MANAGER_FACTORIES)


class BuiltinContextManagerResolver:
    """Resolve built-in Context Managers behind the outer ContextAssembler contract."""

    __slots__ = ("_managers",)

    def __init__(self) -> None:
        self._managers: dict[str, ContextAssembler] = {
            name: ContextManagerRunner(factory())
            for name, factory in _BUILTIN_CONTEXT_MANAGER_FACTORIES.items()
        }

    def resolve(self, name: str) -> ContextAssembler:
        normalized = normalize_context_manager_name(name)
        manager = self._managers.get(normalized)
        if manager is None:
            raise ValueError(f"Unsupported Context Manager: {normalized}")
        return manager


class ResolvedContextAssembler:
    """Snapshot-aware dispatcher used by Model Invocation runtime code."""

    __slots__ = ("_resolver", "_default_name")

    def __init__(
        self,
        resolver: BuiltinContextManagerResolver,
        *,
        default_name: str,
    ) -> None:
        self._resolver = resolver
        self._default_name = normalize_context_manager_name(default_name)

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        selected = getattr(
            request.runtime_context,
            "context_assembler_name",
            None,
        )
        return self._resolver.resolve(
            selected or self._default_name
        ).assemble(request)


def build_context_manager_resolver() -> BuiltinContextManagerResolver:
    return BuiltinContextManagerResolver()


def build_context_assembler(
    name: str = DEFAULT_CONTEXT_MANAGER,
) -> ContextAssembler:
    return build_context_manager_resolver().resolve(name)


def build_runtime_context_assembler(
    default_context_manager: str = DEFAULT_CONTEXT_MANAGER,
) -> ContextAssembler:
    return ResolvedContextAssembler(
        build_context_manager_resolver(),
        default_name=default_context_manager,
    )


__all__ = [
    "BuiltinContextManagerResolver",
    "build_context_assembler",
    "build_context_manager_resolver",
    "build_runtime_context_assembler",
    "builtin_context_manager_names",
]
