from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class ToolInvocationMetrics:
    """Task-local operational metrics for one Tool invocation.

    These values are observability metadata. They must never be injected into the
    logical Tool result consumed by the LLM, Network runtime, or API callers.
    """

    provider_latency_ms: float | None = None


current_tool_invocation_metrics: ContextVar[ToolInvocationMetrics | None] = ContextVar(
    "current_tool_invocation_metrics",
    default=None,
)


def record_tool_provider_latency(value: object) -> None:
    metrics = current_tool_invocation_metrics.get()
    if metrics is None:
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        metrics.provider_latency_ms = float(value)
