from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from modules.agent.application.strategy_sdk import (
    StrategyDecision,
    StrategyDecisionType,
)


DEFAULT_MAX_TOOL_ROUNDS = 5
DEFAULT_MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS = 2


class StandardStopReason(StrEnum):
    REPEATED_SEMANTIC_FAILURES = "repeated semantic capability failures"
    CAPABILITY_ROUND_LIMIT = "capability round limit reached"
    PROVIDER_REJECTED_FOLLOWUP = (
        "the capability follow-up request was rejected by the provider"
    )


@dataclass(frozen=True, slots=True)
class StandardExecutionPolicy:
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS
    max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS

    def __post_init__(self) -> None:
        if self.max_tool_rounds <= 0:
            raise ValueError("max_tool_rounds must be positive")
        if self.max_consecutive_failures <= 0:
            raise ValueError("max_consecutive_failures must be positive")

    def evaluate(self, state) -> StrategyDecision:
        if state.consecutive_failures >= self.max_consecutive_failures:
            return StrategyDecision(
                type=StrategyDecisionType.FINALIZE,
                reason=StandardStopReason.REPEATED_SEMANTIC_FAILURES.value,
            )
        if state.tool_round >= self.max_tool_rounds:
            return StrategyDecision(
                type=StrategyDecisionType.FINALIZE,
                reason=StandardStopReason.CAPABILITY_ROUND_LIMIT.value,
            )
        return StrategyDecision(type=StrategyDecisionType.CONTINUE)
