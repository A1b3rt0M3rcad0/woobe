from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StrategyBootstrap:
    """Runtime-prepared bootstrap inputs that only the Strategy may act on."""

    initial_tool_call: dict[str, Any] | None = None
