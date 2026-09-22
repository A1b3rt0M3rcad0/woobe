from __future__ import annotations

from typing import Generic, Protocol, TypeVar

from modules.agent.application.context_manager_sdk.budget import ContextBudget
from modules.agent.application.context_manager_sdk.candidates import ContextCandidates
from modules.agent.application.context_manager_sdk.capacity import ContextCapacity
from modules.agent.application.context_manager_sdk.checkpoint import ContextCheckpointBoundary
from modules.agent.application.context_manager_sdk.inventory import ContextInventory
from modules.agent.application.context_manager_sdk.invocation import ContextInvocation
from modules.agent.application.context_manager_sdk.outcome import ContextManagerOutcome
from modules.agent.application.context_manager_sdk.pressure import ContextPressure
from modules.agent.application.context_manager_sdk.priorities import ContextPriorities
from modules.agent.application.context_manager_sdk.sources import ContextSources
from modules.agent.application.context_manager_sdk.state import ContextManagerState
from modules.agent.application.context_manager_sdk.summary import ContextSummary
from modules.agent.application.interfaces.context_policy import ContextPolicyV1


StateT = TypeVar("StateT", bound=ContextManagerState)


class ContextManagerContext(Protocol, Generic[StateT]):
    """Stable programmable API exposed to concrete Context Managers."""

    @property
    def policy(self) -> ContextPolicyV1: ...

    state: StateT
    candidates: ContextCandidates
    capacity: ContextCapacity
    inventory: ContextInventory
    invocation: ContextInvocation
    priorities: ContextPriorities
    budget: ContextBudget
    pressure: ContextPressure
    sources: ContextSources
    summary: ContextSummary

    @property
    def has_active_skills(self) -> bool: ...

    async def checkpoint(
        self,
        boundary: ContextCheckpointBoundary = ContextCheckpointBoundary.MANUAL,
    ) -> None: ...

    def complete(self) -> ContextManagerOutcome: ...
