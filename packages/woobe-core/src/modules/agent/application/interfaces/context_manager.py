from __future__ import annotations

from typing import Generic, Protocol, TypeVar, runtime_checkable

from modules.agent.application.context_manager_sdk import (
    ContextManagerContext,
    ContextManagerOutcome,
    ContextManagerState,
)


StateT = TypeVar("StateT", bound=ContextManagerState)


@runtime_checkable
class ContextManager(Protocol, Generic[StateT]):
    """One concrete programmable context-management algorithm."""

    name: str
    state_type: type[StateT]

    async def assemble(
        self,
        ctx: ContextManagerContext[StateT],
    ) -> ContextManagerOutcome: ...
