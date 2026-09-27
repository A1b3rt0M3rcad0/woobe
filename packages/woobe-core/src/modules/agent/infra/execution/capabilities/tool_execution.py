from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Coroutine

from modules.agent.infra.execution.durable_execution_instrumentation import (
    execute_tool_call,
)

ToolExecuteFn = Callable[..., Awaitable[tuple[Any, Any, dict[str, Any]]]]


@dataclass(frozen=True, slots=True)
class ToolExecutionBatch:
    """One durable batch of Tool results produced by a strategy step."""

    results: list[tuple[Any, Any, dict[str, Any]]]
    wall_latency_ms: int
    requires_suspension: bool = False
    suspension_reason: str | None = None
    operation_ref: str | None = None
    suspension_metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ToolExecutionCapability:
    """Execute bound Tools through the runtime-governed durable Tool path."""

    execute_single_tool: Callable[[dict, str], Coroutine[Any, Any, dict]]
    tool_name_to_id: dict[str, str]
    execute_fn: ToolExecuteFn | None = None

    async def execute_many(self, tool_calls: list[dict]) -> ToolExecutionBatch:
        execute = self.execute_fn or execute_tool_call
        started = time.monotonic()
        results = await asyncio.gather(
            *[
                execute(
                    execute=self.execute_single_tool,
                    tool_call=tool_call,
                    resolved_tool_id=self.tool_name_to_id.get(
                        tool_call["name"],
                        tool_call["name"],
                    ),
                )
                for tool_call in tool_calls
            ]
        )
        suspension: dict[str, Any] | None = None
        for _info, _message, payload in results:
            if not isinstance(payload, dict):
                continue
            raw = payload.get("suspension")
            if isinstance(raw, dict) and isinstance(raw.get("reason"), str):
                suspension = raw
                break

        return ToolExecutionBatch(
            results=list(results),
            wall_latency_ms=round((time.monotonic() - started) * 1000),
            requires_suspension=suspension is not None,
            suspension_reason=(
                str(suspension["reason"]) if suspension is not None else None
            ),
            operation_ref=(
                str(suspension["operation_ref"])
                if suspension is not None and suspension.get("operation_ref") is not None
                else None
            ),
            suspension_metadata=(
                dict(suspension.get("metadata") or {})
                if suspension is not None
                else None
            ),
        )
