from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from modules.agent.infra.execution.execution_instrumentation import aggregate_usage


def _cost_details(llm_calls: list[dict[str, Any]]) -> dict[str, Any]:
    pricing_ids: list[Any] = []
    cost_reasons: list[str] = []
    cost_statuses: list[str] = []
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
    return {
        "pricing_ids": pricing_ids,
        "cost_reason": "; ".join(cost_reasons) if cost_reasons else None,
        "cost_statuses": cost_statuses,
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
class DeferredAgentMetrics:
    usage: dict[str, Any]
    diagnostics: dict[str, Any]
    llm_calls: list[dict[str, Any]]
    started_at: str
    completed_at: str


def build_deferred_agent_metrics(context, output) -> DeferredAgentMetrics:
    """Build the Agent-owned v5 telemetry snapshot for deferred Network persistence."""

    execution = context.execution
    llm_calls = list(execution.llm_calls) if execution is not None else []
    aggregate, usage_complete, cost_status = aggregate_usage(llm_calls)
    usage = aggregate.model_dump()

    completed_at = datetime.now(timezone.utc).isoformat()
    total_ms = round((time.monotonic() - context.started_at) * 1000)
    llm_work_ms = sum(int(call.get("latency_ms") or 0) for call in llm_calls)
    tool_wall_ms = int(execution.tool_wall_latency_ms or 0) if execution else 0
    tool_work_ms = int(execution.tool_call_duration_sum_ms or 0) if execution else 0
    provider_work_ms = (
        _tool_provider_work_ms(execution.timeline)
        if execution is not None
        else None
    )
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
    prepare_ms = int(context.prepare_latency_ms or 0)
    other_ms = max(total_ms - prepare_ms - llm_work_ms - tool_wall_ms, 0)
    cost_details = _cost_details(llm_calls)
    tool_calls = list(getattr(output, "tool_calls", None) or [])
    sources = list(getattr(output, "sources", None) or [])
    successful_tool_calls = sum(
        getattr(item, "success", None) is True
        for item in tool_calls
    )
    failed_tool_calls = sum(
        getattr(item, "success", None) is False
        for item in tool_calls
    )

    diagnostics = {
        "schema_version": 5,
        "agent_runtime_latency_ms": total_ms,
        "total_latency_ms": total_ms,
        "prepare_latency_ms": context.prepare_latency_ms,
        "llm_work_latency_ms": llm_work_ms,
        "llm_runtime_latency_ms": llm_work_ms,
        "tool_wall_latency_ms": tool_wall_ms,
        "tool_work_latency_ms": tool_work_ms,
        "tool_call_duration_sum_ms": tool_work_ms,
        "tool_parallelism_ratio": tool_parallelism_ratio,
        "tool_provider_work_ms": provider_work_ms,
        "tool_runtime_overhead_ms": tool_runtime_overhead_ms,
        # Child Agent persistence is deferred to the Network finalizer. Do not
        # attribute the shared Network PostgreSQL commit to every Agent Run.
        "finalization_work_latency_ms": 0,
        "persistence_latency_ms": 0,
        "other_latency_ms": other_ms,
        "unaccounted_latency_ms": other_ms,
        "orchestration_latency_ms": None,
        "llm_call_count": len(llm_calls),
        "tool_call_count": len(tool_calls),
        "successful_tool_calls": successful_tool_calls,
        "failed_tool_calls": failed_tool_calls,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "usage_complete": usage_complete,
        "cost_status": cost_status,
        "cost_usd": usage.get("cost_usd"),
        "cost_reason": cost_details["cost_reason"],
        "cost_statuses": cost_details["cost_statuses"],
        "pricing_ids": cost_details["pricing_ids"],
        "provider_model_id": (
            str(output.provider_model_id)
            if getattr(output, "provider_model_id", None)
            else None
        ),
        "provider_credential_id": (
            str(output.provider_credential_id)
            if getattr(output, "provider_credential_id", None)
            else None
        ),
        "fallback_provider_model_id": (
            str(output.fallback_provider_model_id)
            if getattr(output, "fallback_provider_model_id", None)
            else None
        ),
        "fallback_credential_id": (
            str(output.fallback_credential_id)
            if getattr(output, "fallback_credential_id", None)
            else None
        ),
        "source_count": len(sources),
        "answer_length": len(str(getattr(output, "answer", "") or "")),
        "fallback_used": bool(getattr(output, "fallback_used", False)),
        "execution_context": context.execution_context,
        "agent_release_id": (
            str(context.agent_release_id) if context.agent_release_id else None
        ),
        "agent_release_version": context.agent_release_version,
    }
    return DeferredAgentMetrics(
        usage=usage,
        diagnostics=diagnostics,
        llm_calls=llm_calls,
        started_at=context.execution_started_at,
        completed_at=completed_at,
    )
