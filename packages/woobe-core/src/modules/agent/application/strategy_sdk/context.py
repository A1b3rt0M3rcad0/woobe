from __future__ import annotations

from typing import Any, Generic, Protocol, TypeVar

from modules.agent.application.strategy_sdk.contracts import ExecutionCheckpointBoundary
from modules.agent.application.strategy_sdk.model import StrategyModel, StrategyModelResult
from modules.agent.application.strategy_sdk.outcome import Completed, Suspended
from modules.agent.application.strategy_sdk.tools import StrategyTools, SuspensionReason


StateT = TypeVar("StateT")


class StrategyContext(Protocol, Generic[StateT]):
    """Stable internal API exposed to concrete Execution Strategies."""

    state: StateT
    model: StrategyModel
    tools: StrategyTools

    async def checkpoint(
        self,
        boundary: ExecutionCheckpointBoundary = ExecutionCheckpointBoundary.TOOL,
    ) -> None: ...

    def complete(self, result: StrategyModelResult | Any) -> Completed: ...

    def suspend(
        self,
        *,
        reason: SuspensionReason,
        operation_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Suspended: ...
