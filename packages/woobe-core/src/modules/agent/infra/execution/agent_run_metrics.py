from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from modules.agent.application.dtos.runtime_dtos import UsageInfo
from modules.agent.infra.execution.execution_instrumentation import aggregate_usage


def _id_text(value: Any) -> str | None:
    return str(value) if value else None


def _cost_details(llm_calls: list[dict[str, Any]]) -> dict[str, Any]:
    pricing_ids: list[Any] = []
    cost_reasons: list[str] = []
    cost_statuses: list[str] = []
    first_pricing_snapshot = None
    for call in llm_calls:
        pricing_id = call.get("pricing_id")
        if pricing_id and pricing_id not in pricing_ids:
            pricing_ids.append(pricing_id)
        reason = call.get("cost_reason")
        if isinstance(reason, str) and reason and reason not in cost_reasons:
            cost_reasons.append(reason)
        status = call.get("cost_status")
        if isinstance(status, str) and status and status not in cost_statuses:
            cost_statuses.append(status)
        if first_pricing_snapshot is None and isinstance(call.get("pricing_snapshot"), dict):
            first_pricing_snapshot = call.get("pricing_snapshot")
    return {
        "pricing_ids": pricing_ids,
        "cost_reasons": cost_reasons,
        "cost_statuses": cost_statuses,
        "pricing_id": pricing_ids[0] if pricing_ids else None,
        "cost_reason": "; ".join(cost_reasons) if cost_reasons else None,
        "pricing_snapshot": first_pricing_snapshot,
    }


def _tool_provider_work_ms(timeline: list[dict[str, Any]]) -> int | None:
    values: list[int] = []
    for item in timeline:
        if item.get("kind") != "tool":
            continue
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        value = payload.get("provider_latency_ms")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(round(float(value)))
    return sum(values) if values else None


@dataclass(frozen=True, slots=True)
class AgentRunMetrics:
    usage: UsageInfo
    diagnostics: dict[str, Any]
    cost_details: dict[str, Any]
    llm_calls: list[dict[str, Any]]
    started_at: str
    completed_at: str
    total_latency_ms: int


def build_agent_run_metrics(
    *,
    context: Any,
    execution: Any,
    binding: Any,
    fallback_used: bool,
    finalization_work_ms: int,
    prepare_latency_ms: int | None = None,
    usage: UsageInfo | None = None,
    usage_complete: bool | None = None,
    cost_status: str | None = None,
    completed_at: str | None = None,
) -> AgentRunMetrics:
    """Build the canonical AgentRun v5 telemetry for every persistence mode."""

    llm_calls = list(execution.llm_calls)
    if usage is None or usage_complete is None or cost_status is None:
        aggregated, complete, aggregated_cost_status = aggregate_usage(llm_calls)
        usage = usage or aggregated
        usage_complete = complete if usage_complete is None else usage_complete
        cost_status = aggregated_cost_status if cost_status is None else cost_status

    completed_at = completed_at or datetime.now(timezone.utc).isoformat()
    total_ms = round((time.monotonic() - context.started_at) * 1000)
    llm_work_ms = sum(int(call.get("latency_ms") or 0) for call in llm_calls)
    tool_wall_ms = int(execution.tool_wall_latency_ms or 0)
    tool_work_ms = int(execution.tool_call_duration_sum_ms or 0)
    provider_work_ms = _tool_provider_work_ms(execution.timeline)
    tool_runtime_overhead_ms = (
        max(tool_work_ms - provider_work_ms, 0)
        if provider_work_ms is not None
        else None
    )
    tool_parallelism_ratio = (
        round(tool_work_ms / tool_wall_ms, 3)
        if tool_wall_ms > 0
        else None
    )
    prepare_ms = int(
        context.prepare_latency_ms
        if prepare_latency_ms is None
        else prepare_latency_ms
    )
    other_ms = max(
        total_ms
        - prepare_ms
        - llm_work_ms
        - tool_wall_ms
        - int(finalization_work_ms or 0),
        0,
    )
    cost_details = _cost_details(llm_calls)
    diagnostics = {
        "schema_version": 5,
        "agent_runtime_latency_ms": total_ms,
        "total_latency_ms": total_ms,
        "prepare_latency_ms": prepare_ms,
        "llm_work_latency_ms": llm_work_ms,
        # Legacy alias retained for historical API consumers.
        "llm_runtime_latency_ms": llm_work_ms,
        "tool_wall_latency_ms": tool_wall_ms,
        "tool_work_latency_ms": tool_work_ms,
        # Legacy alias retained for historical API consumers.
        "tool_call_duration_sum_ms": tool_work_ms,
        "tool_parallelism_ratio": tool_parallelism_ratio,
        "tool_provider_work_ms": provider_work_ms,
        "tool_runtime_overhead_ms": tool_runtime_overhead_ms,
        "finalization_work_latency_ms": int(finalization_work_ms or 0),
        # Legacy alias. This is pre-commit finalization work, not DB commit RTT.
        "persistence_latency_ms": int(finalization_work_ms or 0),
        "other_latency_ms": other_ms,
        "unaccounted_latency_ms": other_ms,
        # Never synthesize orchestration from a residual.
        "orchestration_latency_ms": None,
        "llm_call_count": len(llm_calls),
        "tool_call_count": len(execution.tool_calls),
        "usage_complete": bool(usage_complete),
        "cost_status": cost_status,
        "cost_reason": cost_details["cost_reason"],
        "cost_statuses": cost_details["cost_statuses"],
        "pricing_ids": cost_details["pricing_ids"],
        "provider_model_id": _id_text(getattr(binding, "provider_model_id", None)),
        "provider_credential_id": _id_text(
            getattr(binding, "provider_credential_id", None)
        ),
        "fallback_provider_model_id": _id_text(
            getattr(binding, "fallback_provider_model_id", None)
        ),
        "fallback_credential_id": _id_text(
            getattr(binding, "fallback_credential_id", None)
        ),
        "execution_context": context.execution_context,
        "execution_strategy": getattr(context, "execution_strategy", None),
        "agent_release_id": _id_text(context.agent_release_id),
        "agent_release_version": context.agent_release_version,
        # Kept in diagnostics because the deferred Network transport currently
        # materializes this flag from the telemetry snapshot.
        "fallback_used": bool(fallback_used),
    }
    return AgentRunMetrics(
        usage=usage,
        diagnostics=diagnostics,
        cost_details=cost_details,
        llm_calls=llm_calls,
        started_at=context.execution_started_at,
        completed_at=completed_at,
        total_latency_ms=total_ms,
    )
