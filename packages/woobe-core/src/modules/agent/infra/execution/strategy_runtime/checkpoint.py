from __future__ import annotations

from modules.agent.application.strategy_sdk import (
    ExecutionCheckpointBoundary,
    ExecutionState,
    StrategyContextContribution,
)
from modules.agent.infra.execution.capabilities.recovery import StrategyRecoveryCapability
from modules.agent.infra.execution.strategy_runtime.runtime_state import StrategyRuntimeState
from modules.agent.infra.execution.strategy_runtime.state import RuntimeStrategyStateStore


class RuntimeStrategyCheckpoint:
    """Persist Strategy state without exposing recovery plumbing to algorithms."""

    __slots__ = (
        "_recovery",
        "_runtime_state",
        "_state_store",
    )

    def __init__(
        self,
        *,
        recovery: StrategyRecoveryCapability,
        runtime_state: StrategyRuntimeState,
        state_store: RuntimeStrategyStateStore,
    ) -> None:
        self._recovery = recovery
        self._runtime_state = runtime_state
        self._state_store = state_store

    async def save(
        self,
        state: ExecutionState,
        boundary: ExecutionCheckpointBoundary,
    ) -> None:
        cursor = {
            "state": self._state_store.dump(state),
            "next_call_index": self._runtime_state.call_index + 1,
        }
        serialized_contributions = {
            key: {
                "key": contribution.key,
                "source_type": contribution.source_type,
                "content": contribution.content,
                "metadata": dict(contribution.metadata),
                "replaces_message_indexes": list(
                    self._runtime_state.context_replacements.get(key, ())
                ),
            }
            for key, contribution in self._runtime_state.context_contributions.items()
            if isinstance(contribution, StrategyContextContribution)
        }
        await self._recovery.checkpoint(
            phase=boundary.value,
            messages=self._runtime_state.messages,
            base_message_count=self._runtime_state.base_message_count,
            execution=self._runtime_state.execution,
            cursor=cursor,
            context_contributions=serialized_contributions,
        )
