"""Legacy compatibility aliases for the canonical Context Manager registry.

New application/runtime code must import from
`modules.agent.application.context_manager_registry`.
"""

from modules.agent.application.context_manager_registry import (
    DEFAULT_CONTEXT_MANAGER_SETTING,
    ContextManagerDescriptor,
    ContextManagerFactory,
    ContextManagerRegistry,
    ContextManagerRegistryError,
    DuplicateContextManagerError,
    InvalidContextManagerFactoryError,
    InvalidDefaultContextManagerError,
    RegistryContextManager,
    UnknownContextManagerError,
    build_context_manager,
    build_context_manager_registry,
    build_runtime_context_manager,
    canonicalize_context_manager_runtime_config,
    list_context_managers,
    validate_context_manager_runtime_config,
)

ContextAssemblerDescriptor = ContextManagerDescriptor
ContextAssemblerFactory = ContextManagerFactory
ContextAssemblerRegistry = ContextManagerRegistry
ContextAssemblerRegistryError = ContextManagerRegistryError
DuplicateContextAssemblerError = DuplicateContextManagerError
InvalidContextAssemblerFactoryError = InvalidContextManagerFactoryError
UnknownContextAssemblerError = UnknownContextManagerError
RegistryContextAssembler = RegistryContextManager

build_context_assembler = build_context_manager
build_context_assembler_registry = build_context_manager_registry
build_runtime_context_assembler = build_runtime_context_manager
canonicalize_context_assembler_runtime_config = canonicalize_context_manager_runtime_config
list_context_assemblers = list_context_managers
validate_context_assembler_runtime_config = validate_context_manager_runtime_config

__all__ = [
    "DEFAULT_CONTEXT_MANAGER_SETTING",
    "ContextAssemblerDescriptor",
    "ContextAssemblerFactory",
    "ContextAssemblerRegistry",
    "ContextAssemblerRegistryError",
    "DuplicateContextAssemblerError",
    "InvalidContextAssemblerFactoryError",
    "InvalidDefaultContextManagerError",
    "RegistryContextAssembler",
    "UnknownContextAssemblerError",
    "build_context_assembler",
    "build_context_assembler_registry",
    "build_runtime_context_assembler",
    "canonicalize_context_assembler_runtime_config",
    "list_context_assemblers",
    "validate_context_assembler_runtime_config",
]
