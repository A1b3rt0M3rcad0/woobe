from __future__ import annotations

from typing import Protocol

from modules.agent.domain.context import ContextSourceType


class ContextInventory(Protocol):
    """Read-only aggregate view of candidates available before selection."""

    @property
    def total_count(self) -> int: ...

    @property
    def total_units(self) -> int: ...

    @property
    def sources(self) -> tuple[ContextSourceType, ...]: ...

    def count(self, source: ContextSourceType) -> int: ...

    def units(self, source: ContextSourceType) -> int: ...

    def contains(self, source: ContextSourceType) -> bool: ...
