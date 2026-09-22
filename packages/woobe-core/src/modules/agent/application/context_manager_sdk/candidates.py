from __future__ import annotations

from typing import Literal, Protocol

from modules.agent.domain.context import ContextPriority, ContextSourceType


class ContextCandidates(Protocol):
    """Programmable selection operations over candidate context."""

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
        strategy: Literal["none", "content_hash"],
        sources: list[ContextSourceType],
    ) -> None: ...

    def order(
        self,
        *,
        strategy: Literal["preserve_input", "source_priority"],
    ) -> None: ...
