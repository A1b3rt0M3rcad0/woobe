from __future__ import annotations

from typing import Any

from modules.agent.application.strategy_sdk import (
    ExecutionCheckpointBoundary,
    ExecutionState,
)
from modules.agent.infra.execution.capabilities.recovery import StrategyRecoveryCapability
from modules.agent.infra.execution.strategy_runtime.runtime_state import StrategyRuntimeState


class RuntimeStrategyCheckpoint:
    """Persist Strategy state without exposing recovery plumbing to algorithms."""

    __slots__ = (
        "_recovery",
        "_runtime_state",
        "_base_message_count",
    )

    def __init__(
        self,
        *,
        recovery: StrategyRecoveryCapability,
        runtime_state: StrategyRuntimeState,
        base_message_count: int,
    ) -> None:
        self._recovery = recovery
        self._runtime_state = runtime_state
        self._base_message_count = base_message_count

    async def save(
        self,
        state: ExecutionState,
        boundary: ExecutionCheckpointBoundary,
    ) -> None:
        cursor = dict(state.checkpoint_cursor())
        cursor["next_call_index"] = self._runtime_state.call_index + 1
        await self._recovery.checkpoint(
            phase=boundary.value,
            messages=state.checkpoint_messages(),
            base_message_count=self._base_message_count,
            execution=self._runtime_state.execution,
            cursor=cursor,
        )
