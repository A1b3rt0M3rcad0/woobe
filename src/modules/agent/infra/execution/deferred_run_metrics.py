from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.agent.infra.execution.agent_run_metrics import build_agent_run_metrics


@dataclass(frozen=True, slots=True)
class DeferredAgentMetrics:
    usage: dict[str, Any]
    diagnostics: dict[str, Any]
    llm_calls: list[dict[str, Any]]
    started_at: str
    completed_at: str


def build_deferred_agent_metrics(context, output) -> DeferredAgentMetrics:
    """Apply deferred persistence policy to the canonical AgentRun metrics."""

    metrics = build_agent_run_metrics(
        context=context,
        execution=context.execution,
        binding=output,
        fallback_used=bool(getattr(output, "fallback_used", False)),
        # Child persistence is shared by the Network finalizer. Attributing that
        # PostgreSQL work to each child would multiply the same work N times.
        finalization_work_ms=0,
    )
    return DeferredAgentMetrics(
        usage=metrics.usage.model_dump(),
        diagnostics=metrics.diagnostics,
        llm_calls=metrics.llm_calls,
        started_at=metrics.started_at,
        completed_at=metrics.completed_at,
    )
