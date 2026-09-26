from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from modules.agent.application.interfaces.execution import (
    InstrumentedExecution,
    InstrumentedExecutionError,
)
from modules.agent.infra.execution.capabilities.tool_execution import ToolExecutionBatch


def _failure_context(
    context: dict[str, Any] | None,
    *,
    partial_result_available: bool,
) -> dict[str, Any]:
    return {
        **(context or {}),
        "partial_result_available": partial_result_available,
    }


@dataclass(slots=True)
class StrategyRuntimeState:
    """Operational execution state hidden from concrete Strategies."""

    execution: InstrumentedExecution = field(
        default_factory=lambda: InstrumentedExecution(result=None)
    )
    call_index: int = 0
    messages: list[Any] = field(default_factory=list)
    base_message_count: int = 0
    context_contributions: dict[str, Any] = field(default_factory=dict)

    def next_call_index(self) -> int:
        self.call_index += 1
        return self.call_index

    def record_model_call(self, call: dict[str, Any]) -> None:
        self.call_index = max(self.call_index, int(call.get("call_index") or 0))
        self.execution.llm_calls.append(call)
        self.execution.timeline.append(
            {"kind": "llm", "occurred_at": call["occurred_at"], "payload": call}
        )

    def record_model_message(self, message: Any) -> None:
        self.messages.append(message)

    def absorb_model_error(self, exc: InstrumentedExecutionError) -> None:
        self.execution.llm_calls.extend(exc.llm_calls)
        self.execution.timeline.extend(exc.timeline)
        self.execution.failure_context = _failure_context(
            exc.failure_context,
            partial_result_available=bool(self.execution.tool_calls),
        )

    def record_knowledge_call(
        self,
        call: dict[str, Any],
        sources: tuple[Any, ...],
    ) -> None:
        self.execution.knowledge_calls.append(call)
        self.execution.timeline.append(
            {
                "kind": "knowledge",
                "occurred_at": call["occurred_at"],
                "payload": call,
            }
        )
        known = {
            source.model_dump_json()
            for source in self.execution.sources
            if hasattr(source, "model_dump_json")
        }
        for source in sources:
            identity = (
                source.model_dump_json()
                if hasattr(source, "model_dump_json")
                else repr(source)
            )
            if identity in known:
                continue
            self.execution.sources.append(source)
            known.add(identity)

    def record_tool_batch(self, batch: ToolExecutionBatch) -> None:
        self.execution.tool_wall_latency_ms += batch.wall_latency_ms
        for info, message, payload in batch.results:
            self.execution.tool_calls.append(info)
            self.execution.tool_call_duration_sum_ms += int(info.duration_ms or 0)
            self.execution.timeline.append(
                {"kind": "tool", "occurred_at": payload["occurred_at"], "payload": payload}
            )
            self.messages.append(message)
