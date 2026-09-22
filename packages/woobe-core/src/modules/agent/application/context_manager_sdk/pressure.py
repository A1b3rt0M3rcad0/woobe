from __future__ import annotations

from typing import Protocol


class ContextPressure(Protocol):
    """Pressure-classification thresholds recorded in Context evidence."""

    def thresholds(
        self,
        *,
        moderate_at: float,
        high_at: float,
        critical_at: float,
    ) -> None: ...
