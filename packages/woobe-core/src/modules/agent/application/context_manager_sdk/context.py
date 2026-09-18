from __future__ import annotations

from typing import Protocol

from modules.agent.application.context_manager_sdk.contracts import ContextManagerOutcome
from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.domain.context import ContextPriority, ContextSourceType


class ContextCandidates(Protocol):
    """Strategy-facing operations over candidate context."""

    def allow(self, sources: list[ContextSourceType]) -> None: ...

    def recent_session(
        self,
        *,
        max_messages: int,
        max_units: int | None,
    ) -> None: ...

    def cap(
        self,
        source: ContextSourceType,
        max_units: int | None,
    ) -> None: ...

    def require(
        self,
        source: ContextSourceType,
        *,
        priority: ContextPriority = ContextPriority.MANDATORY,
    ) -> None: ...

    def deduplicate(
        self,
        *,
        strategy: str,
        sources: list[ContextSourceType],
    ) -> None: ...

    def order(self, *, strategy: str) -> None: ...


class ContextBudget(Protocol):
    """Budget and pressure controls applied by the shared Context Runtime."""

    def configure(
        self,
        *,
        max_input_units: int | None,
        runtime_reserve_units: int,
    ) -> None: ...

    def pressure(
        self,
        *,
        moderate_at: float,
        high_at: float,
        critical_at: float,
    ) -> None: ...


class ContextSources(Protocol):
    """Optional materialization sources a Manager may enable."""

    def skills(self) -> None: ...


class ContextManagerContext(Protocol):
    """Stable internal API exposed to concrete Context Managers."""

    policy: ContextPolicyV1
    candidates: ContextCandidates
    budget: ContextBudget
    sources: ContextSources

    @property
    def has_active_skills(self) -> bool: ...

    def complete(self) -> ContextManagerOutcome: ...
