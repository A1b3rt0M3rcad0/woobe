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
        return ToolExecutionBatch(
            results=list(results),
            wall_latency_ms=round((time.monotonic() - started) * 1000),
        )
