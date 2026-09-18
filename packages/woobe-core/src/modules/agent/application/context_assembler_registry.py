"""Compatibility facade for the renamed Context Manager product catalog.

New application code should import from context_manager_registry.
"""

from modules.agent.application.context_manager_registry import (
    DEFAULT_CONTEXT_MANAGER_SETTING,
    SUPPORTED_CONTEXT_MANAGERS,
    ContextAssemblerDescriptor,
    ContextAssemblerRegistry,
    DuplicateContextAssemblerError,
    InvalidDefaultContextManagerError,
    UnknownContextAssemblerError,
    build_context_assembler_registry,
    canonicalize_context_assembler_runtime_config,
    list_context_assemblers,
    validate_context_assembler_runtime_config,
)

__all__ = [
    "DEFAULT_CONTEXT_MANAGER_SETTING",
    "SUPPORTED_CONTEXT_MANAGERS",
    "ContextAssemblerDescriptor",
    "ContextAssemblerRegistry",
    "DuplicateContextAssemblerError",
    "InvalidDefaultContextManagerError",
    "UnknownContextAssemblerError",
    "build_context_assembler_registry",
    "canonicalize_context_assembler_runtime_config",
    "list_context_assemblers",
    "validate_context_assembler_runtime_config",
]
