from __future__ import annotations

from typing import Protocol


class ContextCapacity(Protocol):
    """Read-only invocation capacity visible to Context Manager algorithms."""

    @property
    def model_capacity_units(self) -> int | None: ...

    @property
    def reserved_output_units(self) -> int | None: ...

    @property
    def runtime_reserve_units(self) -> int: ...

    @property
    def configured_input_budget_units(self) -> int | None: ...

    @property
    def model_usable_input_units(self) -> int | None: ...

    @property
    def usable_input_budget_units(self) -> int | None: ...

    @property
    def budget_clamped(self) -> bool: ...
