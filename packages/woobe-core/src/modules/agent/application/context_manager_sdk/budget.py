from __future__ import annotations

from typing import Protocol


class ContextBudget(Protocol):
    """Programmable input-budget controls enforced by Context Manager Runtime."""

    def configure(
        self,
        *,
        max_input_units: int | None,
        runtime_reserve_units: int,
    ) -> None: ...
