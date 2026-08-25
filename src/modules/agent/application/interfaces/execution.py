from dataclasses import dataclass, field
from typing import Any

from modules.agent.application.dtos.runtime_dtos import ToolCallInfo


@dataclass
class InstrumentedExecution:
    result: Any
    tool_calls: list[ToolCallInfo] = field(default_factory=list)
    llm_calls: list[dict[str, Any]] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    tool_wall_latency_ms: int = 0
    tool_call_duration_sum_ms: int = 0
    failure_context: dict[str, Any] | None = None


class InstrumentedExecutionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        llm_calls: list[dict[str, Any]] | None = None,
        tool_calls: list[ToolCallInfo] | None = None,
        timeline: list[dict[str, Any]] | None = None,
        tool_wall_latency_ms: int = 0,
        tool_call_duration_sum_ms: int = 0,
        failure_context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.llm_calls = llm_calls or []
        self.tool_calls = tool_calls or []
        self.timeline = timeline or []
        self.tool_wall_latency_ms = tool_wall_latency_ms
        self.tool_call_duration_sum_ms = tool_call_duration_sum_ms
        self.failure_context = failure_context
