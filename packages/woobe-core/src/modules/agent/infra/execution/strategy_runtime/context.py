from __future__ import annotations

from typing import Any, Generic, TypeVar

from modules.agent.application.strategy_sdk import (
    Completed,
    ExecutionCheckpointBoundary,
    ExecutionState,
    StrategyModelResult,
    Suspended,
    SuspensionReason,
)
from modules.agent.infra.execution.strategy_runtime.checkpoint import RuntimeStrategyCheckpoint
from modules.agent.infra.execution.strategy_runtime.model import RuntimeStrategyModel
from modules.agent.infra.execution.strategy_runtime.runtime_state import StrategyRuntimeState
from modules.agent.infra.execution.strategy_runtime.tools import RuntimeStrategyTools


StateT = TypeVar("StateT", bound=ExecutionState)


class RuntimeStrategyContext(Generic[StateT]):
    """Concrete implementation of the stable StrategyContext API."""

    __slots__ = (
        "state",
        "model",
        "tools",
        "_checkpoint",
        "_runtime_state",
    )

    def __init__(
        self,
        *,
        state: StateT,
        model: RuntimeStrategyModel,
        tools: RuntimeStrategyTools,
        checkpoint: RuntimeStrategyCheckpoint,
        runtime_state: StrategyRuntimeState,
    ) -> None:
        self.state = state
        self.model = model
        self.tools = tools
        self._checkpoint = checkpoint
        self._runtime_state = runtime_state

    async def checkpoint(
        self,
        boundary: ExecutionCheckpointBoundary = ExecutionCheckpointBoundary.TOOL,
    ) -> None:
        await self._checkpoint.save(self.state, boundary)

    def complete(self, result: StrategyModelResult | Any) -> Completed:
        self._runtime_state.execution.result = (
            result.message if isinstance(result, StrategyModelResult) else result
        )
        return Completed(self._runtime_state.execution)

    def suspend(
        self,
        *,
        reason: SuspensionReason,
        operation_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Suspended:
        return Suspended(
            reason=reason,
            operation_ref=operation_ref,
            metadata=metadata,
        )
