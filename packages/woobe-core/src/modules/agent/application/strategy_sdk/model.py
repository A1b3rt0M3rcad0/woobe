from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, TypeAlias

from modules.agent.application.strategy_sdk.contracts import ExecutionPhase


StrategyPhase: TypeAlias = str | ExecutionPhase


class StrategyOutputMode(StrEnum):
    INTERNAL = "internal"
    INTERMEDIATE = "intermediate"
    FINAL = "final"


def strategy_phase_value(phase: StrategyPhase) -> str:
    return phase.value if isinstance(phase, ExecutionPhase) else str(phase)


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
        phase: StrategyPhase | None = None,
        directive: str | None = None,
        output_mode: StrategyOutputMode | None = None,
    ) -> StrategyModelResult:
        """Invoke the model for one Strategy phase.

        ``directive`` is an ephemeral execution instruction scoped to this model
        invocation. It refines how the model should operate during the current
        phase without mutating the Agent behavior, objective, Skills, Session, or
        persistent context.
        """
        ...

    async def finalize(
        self,
        *,
        reason: str,
        phase: StrategyPhase,
        directive: str | None = None,
        output_mode: StrategyOutputMode | None = None,
    ) -> StrategyModelResult:
        """Produce a terminal model response for one Strategy phase.

        ``directive`` follows the same invocation-local semantics as ``invoke``.
        """
        ...
