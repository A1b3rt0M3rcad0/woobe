from __future__ import annotations

from modules.agent.application.strategy_sdk import (
    StrategyToolBatch,
    StrategyToolSelection,
    StrategyToolSelectionMode,
)
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

    @property
    def has_any(self) -> bool:
        return bool(self._capability.tool_name_to_id)

    def all(self) -> StrategyToolSelection:
        return StrategyToolSelection(StrategyToolSelectionMode.ALL)

    def none(self) -> StrategyToolSelection:
        return StrategyToolSelection(StrategyToolSelectionMode.NONE)

    def select(self, *names: str) -> StrategyToolSelection:
        normalized = tuple(dict.fromkeys(name.strip() for name in names if name.strip()))
        if not normalized:
            raise ValueError("Tool selection requires at least one tool name")
        unknown = sorted(set(normalized).difference(self._capability.tool_name_to_id))
        if unknown:
            raise ValueError(
                "Execution Strategy selected unauthorized or unknown Tools: "
                + ", ".join(unknown)
            )
        return StrategyToolSelection(
            StrategyToolSelectionMode.EXPLICIT,
            normalized,
        )

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
