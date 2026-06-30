from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

from langchain_core.messages import ToolMessage

from modules.agent.application.dtos.runtime_dtos import ToolCallInfo, UsageInfo
from modules.agent.application.use_cases.runtime_streaming import (
    emit_agent_activity,
    emit_runtime_event,
    invoke_model_with_optional_streaming,
)
from modules.agent.application.use_cases.tool_output_compaction import (
    compact_tool_output_for_llm,
)
from shared.infra.llm_cost import calculate_llm_cost
from shared.infra.llm_usage import normalize_llm_usage


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def tool_http_latency_ms(tool_output: Any) -> float | None:
    if not isinstance(tool_output, dict):
        return None
    direct = tool_output.get("duration_ms")
    if isinstance(direct, (int, float)) and not isinstance(direct, bool):
        return float(direct)
    nested = tool_output.get("output")
    if isinstance(nested, dict):
        value = nested.get("duration_ms")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


@dataclass
class InstrumentedExecution:
    result: Any
    tool_calls: list[ToolCallInfo] = field(default_factory=list)
    llm_calls: list[dict[str, Any]] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    tool_wall_latency_ms: int = 0
    tool_call_duration_sum_ms: int = 0


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
    ) -> None:
        super().__init__(message)
        self.llm_calls = llm_calls or []
        self.tool_calls = tool_calls or []
        self.timeline = timeline or []
        self.tool_wall_latency_ms = tool_wall_latency_ms
        self.tool_call_duration_sum_ms = tool_call_duration_sum_ms


def _cost_context(pricing_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not pricing_snapshot:
        return {
            "provider_model_id": None,
            "provider_credential_id": None,
            "pricing_id": None,
            "pricing_snapshot": None,
        }
    return {
        "provider_model_id": pricing_snapshot.get("provider_model_id"),
        "provider_credential_id": pricing_snapshot.get("provider_credential_id"),
        "pricing_id": pricing_snapshot.get("pricing_id"),
        "pricing_snapshot": pricing_snapshot,
    }


async def invoke_llm(
    *,
    model: Any,
    messages: list,
    phase: str,
    call_index: int,
    provider: str,
    model_name: str,
    pricing_snapshot: dict[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    call_id = str(uuid4())
    started_at = utc_iso()
    started = time.monotonic()
    cost_context = _cost_context(pricing_snapshot)
    try:
        result = await invoke_model_with_optional_streaming(
            model=model,
            messages=messages,
            phase=phase,
            provider=provider,
            model_name=model_name,
        )
    except Exception as exc:
        ended_at = utc_iso()
        call = {
            "call_id": call_id,
            "call_index": call_index,
            "phase": phase,
            "status": "error",
            "error": str(exc),
            "started_at": started_at,
            "ended_at": ended_at,
            "occurred_at": ended_at,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cost_usd": None,
            "cost_status": "unknown_tokens",
            "cost_reason": "LLM call failed before usage could be measured",
            "usage_complete": False,
            "provider": provider,
            "model": model_name,
            **cost_context,
        }
        raise InstrumentedExecutionError(
            str(exc),
            llm_calls=[call],
            timeline=[{"kind": "llm", "occurred_at": ended_at, "payload": call}],
        ) from exc

    ended_at = utc_iso()
    usage = normalize_llm_usage(result)
    complete = all(
        usage.get(field) is not None
        for field in ("input_tokens", "output_tokens", "total_tokens")
    )
    cost = calculate_llm_cost(
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        pricing_snapshot=pricing_snapshot,
    )
    call = {
        "call_id": call_id,
        "call_index": call_index,
        "phase": phase,
        "status": "success",
        "error": None,
        "started_at": started_at,
        "ended_at": ended_at,
        "occurred_at": ended_at,
        "latency_ms": round((time.monotonic() - started) * 1000),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "cost_usd": cost["cost_usd"],
        "cost_status": cost["cost_status"],
        "cost_reason": cost["cost_reason"],
        "usage_complete": complete,
        "provider": provider,
        "model": model_name,
        **cost_context,
    }
    return result, call


async def execute_tool_call(
    *,
    execute: Callable[[dict, str], Awaitable[dict]],
    tool_call: dict,
    resolved_tool_id: str,
) -> tuple[ToolCallInfo, ToolMessage, dict[str, Any]]:
    started_at = utc_iso()
    tool_name = tool_call["name"]
    await emit_agent_activity(
        "calling_tool",
        message=f"Calling tool: {tool_name}...",
        tool_name=tool_name,
    )
    await emit_runtime_event(
        "tool_call_started",
        tool_call_id=tool_call["id"],
        tool_name=tool_name,
        input=tool_call.get("args"),
        status="running",
        started_at=started_at,
    )
    started = time.monotonic()
    output = await execute(tool_call, resolved_tool_id)
    ended_at = utc_iso()
    duration_ms = round((time.monotonic() - started) * 1000)
    success = output.get("success", False) if isinstance(output, dict) else True
    error = output.get("error") if isinstance(output, dict) else None
    llm_content = compact_tool_output_for_llm(output)
    info = ToolCallInfo(
        tool_call_id=tool_call["id"],
        tool_name=tool_name,
        input=tool_call.get("args"),
        output=output,
        duration_ms=duration_ms,
        success=success,
        error=error,
    )
    message = ToolMessage(
        content=llm_content,
        tool_call_id=tool_call["id"],
    )
    payload = {
        "tool_call_id": tool_call["id"],
        "tool_name": tool_name,
        "input": tool_call.get("args"),
        "output": output,
        "llm_output_size_chars": len(llm_content),
        "duration_ms": duration_ms,
        "http_latency_ms": tool_http_latency_ms(output),
        "success": success,
        "error": error,
        "status": "success" if success else "error",
        "started_at": started_at,
        "ended_at": ended_at,
        "occurred_at": ended_at,
    }
    await emit_runtime_event("tool_call_completed", **payload)
    await emit_agent_activity(
        "processing_tool_result",
        message="Processing tool result...",
        tool_name=tool_name,
    )
    return info, message, payload


def _sum_int_field(calls: list[dict[str, Any]], field: str) -> int | None:
    values: list[int] = []
    for call in calls:
        value = call.get(field)
        if not isinstance(value, int) or isinstance(value, bool):
            return None
        values.append(value)
    return sum(values)


def _sum_known_costs(calls: list[dict[str, Any]]) -> float | None:
    values: list[float] = []
    for call in calls:
        value = call.get("cost_usd")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    if not values:
        return None
    return sum(values)


def _aggregate_cost_status(successful: list[dict[str, Any]], total_call_count: int) -> str:
    if not successful or len(successful) != total_call_count:
        return "partial" if successful else "unknown"
    statuses = {str(call.get("cost_status") or "unknown") for call in successful}
    if statuses == {"known"}:
        return "known"
    if "known" in statuses:
        return "partial"
    if "unknown_tokens" in statuses:
        return "unknown_tokens"
    if "unknown_pricing" in statuses:
        return "unknown_pricing"
    return "unknown"


def aggregate_usage(
    llm_calls: list[dict[str, Any]],
) -> tuple[UsageInfo, bool, str]:
    successful = [call for call in llm_calls if call.get("status") == "success"]
    complete = bool(llm_calls) and len(successful) == len(llm_calls) and all(
        call.get("usage_complete") is True for call in successful
    )
    input_tokens = _sum_int_field(successful, "input_tokens") if complete else None
    output_tokens = _sum_int_field(successful, "output_tokens") if complete else None
    total_tokens = _sum_int_field(successful, "total_tokens") if complete else None
    cost_usd = _sum_known_costs(successful)
    cost_status = _aggregate_cost_status(successful, len(llm_calls))

    return (
        UsageInfo(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
        ),
        complete,
        cost_status,
    )
