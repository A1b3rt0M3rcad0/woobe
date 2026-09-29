from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypeAlias

from modules.agent.application.strategy_sdk.contracts import ExecutionPhase
from modules.agent.application.strategy_sdk.invocation import StrategyInvocation
from modules.agent.application.strategy_sdk.tools import StrategyToolCall
from modules.agent.domain.model_spec import ModelSpec


StrategyPhase: TypeAlias = str | ExecutionPhase


def strategy_phase_value(phase: StrategyPhase) -> str:
    return phase.value if isinstance(phase, ExecutionPhase) else str(phase)


def strategy_phase_with_iteration(phase: StrategyPhase, iteration: int) -> str:
    if iteration <= 0:
        raise ValueError("Execution Strategy phase iteration must be positive")
    return f"{strategy_phase_value(phase)}_{iteration}"


@dataclass(frozen=True, slots=True)
class StrategyModelResult:
    """Framework-neutral Model result exposed to Execution Strategies."""

    content: Any
    tool_calls: tuple[StrategyToolCall, ...] = ()
    finish_reason: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class StrategyModel(Protocol):
    """Model operations available to an Execution Strategy."""

    @property
    def spec(self) -> ModelSpec: ...

    @property
    def fallback_available(self) -> bool: ...

    async def invoke(
        self,
        invocation: StrategyInvocation,
    ) -> StrategyModelResult: ...

    async def invoke_fallback(
        self,
        invocation: StrategyInvocation,
        *,
        primary_error: str,
    ) -> StrategyModelResult: ...

    async def finalize(
        self,
        invocation: StrategyInvocation,
        *,
        reason: str,
    ) -> StrategyModelResult: ...
