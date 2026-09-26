from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

from modules.agent.application.strategy_sdk.contracts import ExecutionPhase

if TYPE_CHECKING:
    from modules.agent.application.strategy_sdk.context_manager import (
        StrategyInvocationContext,
    )
    from modules.agent.application.strategy_sdk.tools import StrategyToolSelection


StrategyPhase: TypeAlias = str | ExecutionPhase


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

    @property
    def fallback_available(self) -> bool: ...

    async def invoke(
        self,
        *,
        context: StrategyInvocationContext,
        phase: StrategyPhase,
        tools: StrategyToolSelection | None = None,
    ) -> StrategyModelResult: ...

    async def invoke_fallback(
        self,
        *,
        context: StrategyInvocationContext,
        primary_error: str,
        phase: StrategyPhase,
        tools: StrategyToolSelection | None = None,
    ) -> StrategyModelResult: ...

    async def finalize(
        self,
        *,
        reason: str,
        phase: StrategyPhase,
        context: StrategyInvocationContext,
        tools: StrategyToolSelection | None = None,
    ) -> StrategyModelResult: ...
