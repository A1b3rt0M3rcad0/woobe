from __future__ import annotations

from modules.agent.application.interfaces.context_assembler import ContextAssemblyRequest
from modules.agent.infra.context_management.manager_runtime.context import (
    RuntimeContextManagerContext,
)


def build_context_manager_context(
    request: ContextAssemblyRequest,
) -> RuntimeContextManagerContext:
    """Build one isolated programmable Manager context for a Model Invocation."""

    return RuntimeContextManagerContext(request)


__all__ = ["build_context_manager_context"]
