from __future__ import annotations

from typing import Protocol

from modules.agent.application.context_manager_sdk.budget import ContextBudget
from modules.agent.application.context_manager_sdk.candidates import ContextCandidates
from modules.agent.application.context_manager_sdk.outcome import ContextManagerOutcome
from modules.agent.application.context_manager_sdk.sources import ContextSources
from modules.agent.application.interfaces.context_policy import ContextPolicyV1


class ContextManagerContext(Protocol):
    """Stable internal API exposed to concrete Context Managers."""

    policy: ContextPolicyV1
    candidates: ContextCandidates
    budget: ContextBudget
    sources: ContextSources

    @property
    def has_active_skills(self) -> bool: ...

    def complete(self) -> ContextManagerOutcome: ...
