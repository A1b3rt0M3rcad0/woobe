from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeAlias

from modules.agent.application.strategy_sdk.tools import SuspensionReason


@dataclass(frozen=True, slots=True)
class Completed:
    result: Any


@dataclass(frozen=True, slots=True)
class Suspended:
    reason: SuspensionReason
    operation_ref: str | None = None
    metadata: dict[str, Any] | None = None


StrategyOutcome: TypeAlias = Completed | Suspended
