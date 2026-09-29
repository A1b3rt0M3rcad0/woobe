from __future__ import annotations

from modules.agent.application.strategy_sdk import (
    StrategyToolBatch,
    StrategyToolCall,
    StrategyToolResult,
    StrategyToolSelection,
    StrategyToolSelectionMode,
    SuspensionReason,
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


    async def execute_many(
        self,
        tool_calls: list[StrategyToolCall] | tuple[StrategyToolCall, ...],
    ) -> StrategyToolBatch:
        batch = await self._capability.execute_many(
            [tool_call.as_runtime_dict() for tool_call in tool_calls]
        )
        self._runtime_state.record_tool_batch(batch)
        results = tuple(
            StrategyToolResult(
                tool_call_id=(
                    str(value)
                    if (value := getattr(info, "tool_call_id", None)) is not None
                    else requested.id
                ),
                tool_name=str(getattr(info, "tool_name", None) or requested.name),
                arguments=dict(requested.arguments),
                output=getattr(info, "output", _payload),
                success=bool(getattr(info, "success", True)),
                status=getattr(info, "status", None),
                error_code=getattr(info, "error_code", None),
                error=getattr(info, "error", None),
            )
            for requested, (info, _message, _payload) in zip(
                tool_calls,
                batch.results,
                strict=True,
            )
        )
        return StrategyToolBatch(
            results=results,
            has_failures=any(not result.success for result in results),
            requires_suspension=batch.requires_suspension,
            suspension_reason=(
                SuspensionReason(batch.suspension_reason)
                if batch.suspension_reason is not None
                else None
            ),
            operation_ref=batch.operation_ref,
            suspension_metadata=batch.suspension_metadata,
        )
