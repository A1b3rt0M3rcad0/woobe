from __future__ import annotations

from typing import Protocol, runtime_checkable

from modules.agent.application.context_manager_sdk import (
    ContextManagerContext,
    ContextManagerOutcome,
)


@runtime_checkable
class ContextManager(Protocol):
    """One concrete algorithm for assembling Model Invocation context."""

    name: str

    def assemble(
        self,
        ctx: ContextManagerContext,
    ) -> ContextManagerOutcome: ...
