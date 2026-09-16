from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


StrategyPhase = str | StrEnum


def strategy_phase_value(phase: StrategyPhase) -> str:
    return phase.value if isinstance(phase, StrEnum) else str(phase)


def strategy_phase_with_iteration(phase: StrategyPhase, iteration: int) -> str:
    if iteration <= 0:
        raise ValueError("Execution Strategy phase iteration must be positive")
    return f"{strategy_phase_value(phase)}_{iteration}"


@dataclass(frozen=True, slots=True)
class StrategyModelResult:
    """Framework-neutral model result exposed to Execution Strategies."""

    message: Any

    @property
    def content(self) -> Any:
        return getattr(self.message, "content", None)

    @property
    def tool_calls(self) -> tuple[dict[str, Any], ...]:
        value = getattr(self.message, "tool_calls", None) or []
        return tuple(item for item in value if isinstance(item, dict))

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class StrategyModel(Protocol):
    """Model operations available to an Execution Strategy."""

    async def invoke(
        self,
        *,
        messages: list[Any],
        phase: StrategyPhase,
    ) -> StrategyModelResult: ...

    async def finalize(
        self,
        *,
        messages: list[Any],
        reason: str,
        phase: StrategyPhase,
    ) -> StrategyModelResult: ...
