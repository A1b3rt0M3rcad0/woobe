from __future__ import annotations

from typing import Protocol


class ContextBudget(Protocol):
    """Programmable budget controls enforced by the shared Context Manager Runtime."""

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
