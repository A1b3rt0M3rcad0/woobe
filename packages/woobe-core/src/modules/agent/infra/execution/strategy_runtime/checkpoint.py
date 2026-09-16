from __future__ import annotations

from typing import Any

from modules.agent.application.strategy_sdk import StrategyStateCodec
from modules.agent.infra.execution.capabilities.recovery import StrategyRecoveryCapability
from modules.agent.infra.execution.strategy_runtime.runtime_state import (
    StrategyRuntimeState,
)


class RuntimeStrategyCheckpoint:
    """Persist strategy-owned state without exposing recovery plumbing to algorithms."""

    __slots__ = (
        "_recovery",
        "_runtime_state",
        "_state_codec",
        "_base_message_count",
    )

    def __init__(
        self,
        *,
        recovery: StrategyRecoveryCapability,
        runtime_state: StrategyRuntimeState,
        state_codec: StrategyStateCodec[Any],
        base_message_count: int,
    ) -> None:
        self._recovery = recovery
        self._runtime_state = runtime_state
        self._state_codec = state_codec
        self._base_message_count = base_message_count

    async def save(self, state: Any) -> None:
        cursor = dict(self._state_codec.dump_cursor(state))
        cursor["next_call_index"] = self._runtime_state.call_index + 1
        await self._recovery.checkpoint(
            phase=self._state_codec.checkpoint_phase(state),
            messages=self._state_codec.messages(state),
            base_message_count=self._base_message_count,
            execution=self._runtime_state.execution,
            cursor=cursor,
        )
