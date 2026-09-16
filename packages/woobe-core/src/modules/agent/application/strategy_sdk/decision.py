from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StrategyDecisionType(StrEnum):
    CONTINUE = "continue"
    FINALIZE = "finalize"


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    type: StrategyDecisionType
    reason: str | None = None
