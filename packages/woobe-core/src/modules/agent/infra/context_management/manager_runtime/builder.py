from __future__ import annotations

from modules.agent.application.interfaces.context_assembler import ContextAssemblyRequest
from modules.agent.application.interfaces.context_manager import ContextManager
from modules.agent.infra.context_management.manager_runtime.checkpoint import (
    RuntimeContextCheckpoint,
)
from modules.agent.infra.context_management.manager_runtime.context import (
    RuntimeContextManagerContext,
)
from modules.agent.infra.context_management.manager_runtime.state import (
    RuntimeContextManagerStateStore,
)
from modules.agent.infra.context_management.manager_runtime.summary import (
    RuntimeContextSummary,
)


def _checkpoint_state_from_runtime(request: ContextAssemblyRequest) -> object:
    value = getattr(request.runtime_context, "context_manager_state", None)
    if isinstance(value, dict):
        return value

    resume = getattr(request.runtime_context, "resume_state", None)
    if isinstance(resume, dict):
        nested = resume.get("context_manager_state")
        if isinstance(nested, dict):
            return nested
    return None


def build_context_manager_context(
    manager: ContextManager,
    request: ContextAssemblyRequest,
) -> RuntimeContextManagerContext:
    """Build one isolated programmable Manager context for a Model Invocation."""

    state_store = RuntimeContextManagerStateStore()
    state = state_store.create(
        manager.state_type,
        _checkpoint_state_from_runtime(request),
        manager_name=manager.name,
    )
    return RuntimeContextManagerContext(
        request,
        state=state,
        summary=RuntimeContextSummary(request),
        checkpoint=RuntimeContextCheckpoint(
            manager_name=manager.name,
            runtime_context=request.runtime_context,
            state_store=state_store,
        ),
    )


__all__ = ["build_context_manager_context"]
