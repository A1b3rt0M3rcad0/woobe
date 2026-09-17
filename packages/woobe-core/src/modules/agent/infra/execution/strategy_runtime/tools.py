from __future__ import annotations

from modules.agent.application.strategy_sdk import StrategyToolBatch
from modules.agent.infra.execution.capabilities.tool_execution import (
    ToolExecutionCapability,
)
from modules.agent.infra.execution.strategy_runtime.runtime_state import (
    StrategyRuntimeState,
)


class RuntimeStrategyTools:
    """Strategy-facing Tool facade backed by governed durable Tool execution."""

    __slots__ = ("_capability", "_runtime_state")

    def __init__(
        self,
        *,
        capability: ToolExecutionCapability,
        runtime_state: StrategyRuntimeState,
    ) -> None:
        self._capability = capability
        self._runtime_state = runtime_state

    async def execute_many(
        self,
        tool_calls: list[dict] | tuple[dict, ...],
    ) -> StrategyToolBatch:
        batch = await self._capability.execute_many(list(tool_calls))
        self._runtime_state.record_tool_batch(batch)
        return StrategyToolBatch(
            results=tuple(payload for _info, _message, payload in batch.results),
            messages=tuple(message for _info, message, _payload in batch.results),
            has_failures=any(
                info.success is False for info, _message, _payload in batch.results
            ),
        )
