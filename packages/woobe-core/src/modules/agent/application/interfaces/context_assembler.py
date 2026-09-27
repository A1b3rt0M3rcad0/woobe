"""Legacy compatibility aliases for the canonical Context Manager contract.

New runtime/application code must import from
`modules.agent.application.interfaces.context_manager`.
"""

from modules.agent.application.interfaces.context_manager import (
    DEFAULT_CONTEXT_MANAGER_KEY,
    STANDARD_CONTEXT_MANAGER_KEY,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
    ContextBudgetExceeded,
    ContextCompactionOutput,
    ContextCompactionRequest,
    ContextInspectionOutput,
    ContextInspectionRequest,
    ContextInvocationEnvironment,
    ContextManagedContribution,
    ContextManager,
    ContextManagerCapabilities,
    ContextManagerKey,
    ContextSummaryOutput,
    ContextSummaryRequest,
    context_manager_key_from_runtime_config,
)

# Compatibility surface for callers persisted before the Context Manager ontology
# became canonical. Internal code must not depend on these aliases.
ContextAssembler = ContextManager
ContextAssemblerKey = ContextManagerKey
STANDARD_CONTEXT_ASSEMBLER_KEY = STANDARD_CONTEXT_MANAGER_KEY
DEFAULT_CONTEXT_ASSEMBLER_KEY = DEFAULT_CONTEXT_MANAGER_KEY
context_assembler_key_from_runtime_config = context_manager_key_from_runtime_config

__all__ = [
    "ContextAssembler",
    "ContextAssemblerKey",
    "STANDARD_CONTEXT_ASSEMBLER_KEY",
    "DEFAULT_CONTEXT_ASSEMBLER_KEY",
    "context_assembler_key_from_runtime_config",
    "ContextAssemblyOutput",
    "ContextAssemblyRequest",
    "ContextBudgetExceeded",
    "ContextCompactionOutput",
    "ContextCompactionRequest",
    "ContextInspectionOutput",
    "ContextInspectionRequest",
    "ContextInvocationEnvironment",
    "ContextManagedContribution",
    "ContextManagerCapabilities",
    "ContextSummaryOutput",
    "ContextSummaryRequest",
]
