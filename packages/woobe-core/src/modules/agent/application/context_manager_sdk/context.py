from __future__ import annotations

from typing import Protocol

from modules.agent.application.context_manager_sdk.budget import ContextBudget
from modules.agent.application.context_manager_sdk.candidates import ContextCandidates
from modules.agent.application.context_manager_sdk.capacity import ContextCapacity
from modules.agent.application.context_manager_sdk.inventory import ContextInventory
from modules.agent.application.context_manager_sdk.invocation import ContextInvocation
from modules.agent.application.context_manager_sdk.outcome import ContextManagerOutcome
from modules.agent.application.context_manager_sdk.pressure import ContextPressure
from modules.agent.application.context_manager_sdk.priorities import ContextPriorities
from modules.agent.application.context_manager_sdk.sources import ContextSources
from modules.agent.application.interfaces.context_policy import ContextPolicyV1


class ContextManagerContext(Protocol):
    """Stable internal API exposed to concrete Context Managers.

    policy is the configured per-invocation policy snapshot and is algorithm input.
    Concrete Managers should treat it as read-only. Effective decisions are
    expressed through SDK primitives and frozen by complete().
    """

    @property
    def policy(self) -> ContextPolicyV1: ...

    candidates: ContextCandidates
    capacity: ContextCapacity
    inventory: ContextInventory
    invocation: ContextInvocation
    priorities: ContextPriorities
    budget: ContextBudget
    pressure: ContextPressure
    sources: ContextSources

    @property
    def has_active_skills(self) -> bool: ...

    def complete(self) -> ContextManagerOutcome: ...
