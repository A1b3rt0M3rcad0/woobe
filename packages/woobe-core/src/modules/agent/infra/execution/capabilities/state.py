from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.infra.execution.capabilities.tool_execution import ToolExecutionBatch


@dataclass(slots=True)
class StrategyExecutionState:
    """Mutable execution-local state owned by one execution strategy."""

    messages: list
    execution: InstrumentedExecution = field(
        default_factory=lambda: InstrumentedExecution(result=None)
    )
    result: Any | None = None
    call_index: int = 0
    iteration: int = 0

    def record_model_result(
        self,
        *,
        result: Any,
        call: dict[str, Any],
    ) -> None:
        self.result = result
        self.call_index = max(self.call_index, int(call.get("call_index") or 0))
        self.execution.llm_calls.append(call)
        self.execution.timeline.append(
            {"kind": "llm", "occurred_at": call["occurred_at"], "payload": call}
        )

    def record_tool_batch(self, batch: ToolExecutionBatch) -> None:
        self.execution.tool_wall_latency_ms += batch.wall_latency_ms
        for info, message, payload in batch.results:
            self.execution.tool_calls.append(info)
            self.execution.tool_call_duration_sum_ms += int(info.duration_ms or 0)
            self.execution.timeline.append(
                {"kind": "tool", "occurred_at": payload["occurred_at"], "payload": payload}
            )
            self.messages.append(message)

    def finish(self) -> InstrumentedExecution:
        self.execution.result = self.result
        return self.execution
