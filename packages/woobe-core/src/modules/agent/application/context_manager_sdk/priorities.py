from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from modules.agent.domain.context import ContextPriority, ContextSourceType


class ContextPriorities(Protocol):
    """Programmable source priorities used by ordering and overflow handling."""

    def set(
        self,
        source: ContextSourceType,
        priority: ContextPriority,
    ) -> None: ...

    def configure(
        self,
        priorities: Mapping[ContextSourceType, ContextPriority],
    ) -> None: ...
