from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import uuid6
from langchain_core.messages import ToolMessage

from modules.agent.application.context_assembly import (
    enrich_snapshot_with_reported_usage,
    estimate_input_units,
    snapshot_to_dict,
)
from modules.agent.application.context_policy import ContextPolicyV1
from modules.agent.application.dtos.runtime_dtos import ToolCallInfo, UsageInfo
from modules.agent.application.interfaces.context_assembler import (
    ContextAssembler,
    ContextAssemblyRequest,
)
from modules.agent.application.interfaces.execution import (
    InstrumentedExecution,
    InstrumentedExecutionError,
)
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.skill_runtime import SKILL_TOOL_NAMES
from modules.agent.application.use_cases.tool_output_compaction import (
    compact_tool_output_for_llm,
)
from modules.agent.application.use_cases.tool_result_semantics import (
    normalize_tool_result,
)
from modules.agent.infra.execution.runtime_streaming import (
    emit_agent_activity,
    emit_runtime_event,
    invoke_model_with_optional_streaming,
)
from modules.agent.infra.execution.tool_invocation_metrics import (
    ToolInvocationMetrics,
    current_tool_invocation_metrics,
)
from shared.contracts.llm_cost import calculate_llm_cost
from shared.contracts.llm_usage import normalize_llm_usage


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _positive_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value)
        return parsed if parsed > 0 else None
    return None


def _provider_failure_context(
    exception: Exception,
    *,
    phase: str,
    call_index: int,
    provider: str,
    model_name: str,
) -> dict[str, Any]:
    status = getattr(exception, "status_code", None)
    response = getattr(exception, "response", None)
    if status is None and response is not None:
        status = getattr(response, "status_code", None)
    code = getattr(exception, "code", None)
    body = getattr(exception, "body", None)
    if code is None and isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            code = error.get("code") or error.get("type")
    return {
        "phase": phase,
        "call_index": call_index,
        "provider": provider,
        "model": model_name,
        "upstream_status": status if isinstance(status, int) else None,
        "upstream_error_code": str(code) if code else None,
    }


def _live_execution() -> InstrumentedExecution | None:
    context = current_execution.get()
    execution = context.execution if context is not None else None
    return execution if isinstance(execution, InstrumentedExecution) else None


def _record_live_llm_call(call: dict[str, Any]) -> None:
    execution = _live_execution()
    if execution is None:
        return
    call_id = call.get("call_id")
    if call_id:
        for existing in execution.llm_calls:
            if existing.get("call_id") == call_id:
                existing.clear()
                existing.update(call)
                for item in execution.timeline:
                    payload = item.get("payload")
                    if (
                        item.get("kind") == "llm"
                        and isinstance(payload, dict)
                        and payload.get("call_id") == call_id
                    ):
                        item["occurred_at"] = call["occurred_at"]
                        item["payload"] = existing
                        return
                execution.timeline.append(
                    {"kind": "llm", "occurred_at": call["occurred_at"], "payload": existing}
                )
                return
    execution.llm_calls.append(call)
    execution.timeline.append(
        {"kind": "llm", "occurred_at": call["occurred_at"], "payload": call}
    )


def _record_live_tool_call(
    info: ToolCallInfo,
    payload: dict[str, Any],
) -> None:
    execution = _live_execution()
    if execution is None:
        return
    call_id = info.tool_call_id
    if call_id and any(item.tool_call_id == call_id for item in execution.tool_calls):
        return
    execution.tool_calls.append(info)
    execution.tool_call_duration_sum_ms += int(info.duration_ms or 0)
    execution.timeline.append(
        {"kind": "tool", "occurred_at": payload["occurred_at"], "payload": payload}
    )


def _assemble_invocation_context(
    *,
    invocation_id,
    messages: list,
    provider: str,
    model_name: str,
    phase: str,
    pricing_snapshot: dict[str, Any] | None,
    context_assembler: ContextAssembler | None,
):
    context = current_execution.get()
    if context is None or context.run_id is None or context.project_id is None:
        return messages, None
    if context_assembler is None:
        raise RuntimeError(
            "ContextAssembler dependency is required for instrumented Agent execution"
        )

    policy = ContextPolicyV1.model_validate(context.context_policy or {})
    previous_capacity = context.model_capacity_units
    previous_tools = context.active_tool_definitions
    # Capacity is invocation-specific. A fallback must not inherit the primary
    # model context window when its ProviderModel metadata does not define one.
    context.model_capacity_units = _positive_int(
        (pricing_snapshot or {}).get("context_window")
    )
    if phase in {"final_response_generation", "json_repair"}:
        context.active_tool_definitions = []
    try:
        assembled = context_assembler.assemble(
            ContextAssemblyRequest(
                messages=messages,
                model_invocation_id=invocation_id,
                agent_run_id=context.run_id,
                project_id=context.project_id,
                provider=provider,
                model=model_name,
                runtime_context=context,
                policy=policy,
            )
        )
        return assembled.messages, assembled.snapshot
    finally:
        context.model_capacity_units = previous_capacity
        context.active_tool_definitions = previous_tools


async def invoke_llm(
    *,
    model: Any,
    messages: list,
    phase: str,
    call_index: int,
    provider: str,
    model_name: str,
    pricing_snapshot: dict[str, Any] | None = None,
    context_assembler: ContextAssembler | None = None,
) -> tuple[Any, dict[str, Any]]:
    call_uuid = uuid6.uuid7()
    call_id = str(call_uuid)
    invocation_messages, context_snapshot = _assemble_invocation_context(
        invocation_id=call_uuid,
        messages=messages,
        provider=provider,
        model_name=model_name,
        phase=phase,
        pricing_snapshot=pricing_snapshot,
        context_assembler=context_assembler,
    )
    started_at = utc_iso()
    started = time.monotonic()
    cost_context = _cost_context(pricing_snapshot)
    running_call = {
        "call_id": call_id,
        "call_index": call_index,
        "phase": phase,
        "status": "running",
        "error": None,
        "started_at": started_at,
        "ended_at": None,
        "occurred_at": started_at,
        "latency_ms": 0,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "cost_usd": None,
        "cost_status": "unknown_tokens",
        "cost_reason": "Model invocation is still in progress",
        "usage_complete": False,
        "provider": provider,
        "model": model_name,
        "context_snapshot": (
            snapshot_to_dict(context_snapshot)
            if context_snapshot is not None
            else None
        ),
        **cost_context,
    }
    _record_live_llm_call(running_call)
    try:
        result = await invoke_model_with_optional_streaming(
            model=model,
            messages=invocation_messages,
            phase=phase,
            provider=provider,
            model_name=model_name,
        )
    except asyncio.CancelledError:
        ended_at = utc_iso()
        call = {
            **running_call,
            "status": "cancelled",
            "ended_at": ended_at,
            "occurred_at": ended_at,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "cost_reason": "Model invocation was cancelled before final provider usage",
        }
        _record_live_llm_call(call)
        raise
    except Exception as exc:
        ended_at = utc_iso()
        failure_context = _provider_failure_context(
            exc,
            phase=phase,
            call_index=call_index,
            provider=provider,
            model_name=model_name,
        )
        call = {
            **running_call,
            "status": "error",
            "error": str(exc),
            "ended_at": ended_at,
            "occurred_at": ended_at,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "cost_reason": "LLM call failed before usage could be measured",
            **failure_context,
        }
        _record_live_llm_call(call)
        raise InstrumentedExecutionError(
            str(exc),
            llm_calls=[call],
            timeline=[{"kind": "llm", "occurred_at": ended_at, "payload": call}],
            failure_context=failure_context,
        ) from exc

    ended_at = utc_iso()
    usage = normalize_llm_usage(result)
    if context_snapshot is not None:
        context_snapshot = enrich_snapshot_with_reported_usage(
            context_snapshot,
            usage.get("input_tokens"),
        )
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
        **running_call,
        "status": "success",
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
        "context_snapshot": (
            snapshot_to_dict(context_snapshot)
            if context_snapshot is not None
            else None
        ),
    }
    _record_live_llm_call(call)
    return result, call


async def execute_tool_call(
    *,
    execute: Callable[[dict, str], Awaitable[dict]],
    tool_call: dict,
    resolved_tool_id: str,
) -> tuple[ToolCallInfo, ToolMessage, dict[str, Any]]:
    started_at = utc_iso()
    tool_name = tool_call["name"]
    is_skill = tool_name in SKILL_TOOL_NAMES
    skill_action = {
        "skills_search": "Searching Skills...",
        "skills_activate": "Activating Skill...",
        "skills_read_resource": "Reading Skill resource...",
    }.get(tool_name)
    await emit_agent_activity(
        "calling_tool",
        message=skill_action or f"Calling tool: {tool_name}...",
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
    metrics = ToolInvocationMetrics()
    metrics_token = current_tool_invocation_metrics.set(metrics)
    started = time.monotonic()
    try:
        output = await execute(tool_call, resolved_tool_id)
    finally:
        current_tool_invocation_metrics.reset(metrics_token)
    ended_at = utc_iso()
    duration_ms = round((time.monotonic() - started) * 1000)
    normalized = normalize_tool_result(output)
    llm_value = output if normalized.success else {
        "success": False,
        "error_code": normalized.error_code,
        "error": normalized.error_message,
        "result": output,
    }
    llm_content = compact_tool_output_for_llm(llm_value)
    raw_units = estimate_input_units(llm_value)
    materialized_units = estimate_input_units(llm_content)
    compacted = materialized_units < raw_units
    info = ToolCallInfo(
        tool_call_id=tool_call["id"],
        tool_name=tool_name,
        input=tool_call.get("args"),
        output=output,
        duration_ms=duration_ms,
        success=normalized.success,
        status=normalized.status,
        error_code=normalized.error_code,
        error=normalized.error_message,
    )
    message = ToolMessage(
        content=llm_content,
        tool_call_id=tool_call["id"],
        additional_kwargs={
            "woobe_context": {
                "source_type": "TOOL",
                "source_ref": str(tool_call["id"]),
                "raw_units": raw_units,
                "selection_method": "tool_result_materialization",
                "transformations": ["tool_output_compaction"] if compacted else [],
                "trust": "authenticated_external",
                "sensitivity": "internal",
                "tool_name": tool_name,
            }
        },
    )
    payload = {
        "tool_call_id": tool_call["id"],
        "tool_name": tool_name,
        "input": tool_call.get("args"),
        "output": output,
        "llm_output_size_chars": len(llm_content),
        "context_raw_units": raw_units,
        "context_materialized_units": materialized_units,
        "context_compacted": compacted,
        "duration_ms": duration_ms,
        "provider_latency_ms": metrics.provider_latency_ms,
        "success": normalized.success,
        "error_code": normalized.error_code,
        "error": normalized.error_message,
        "status": normalized.status,
        "started_at": started_at,
        "ended_at": ended_at,
        "occurred_at": ended_at,
    }
    if is_skill and isinstance(output.get("output"), dict):
        receipt = output["output"]
        for source, target in (("name", "skill_name"), ("version", "skill_version")):
            if isinstance(receipt.get(source), str):
                payload[target] = receipt[source]
    _record_live_tool_call(info, payload)
    await emit_runtime_event("tool_call_completed", **payload)
    await emit_agent_activity(
        "processing_tool_result",
        message="Processing Skill result..." if is_skill else "Processing tool result...",
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


def _sum_available_int_field(calls: list[dict[str, Any]], field: str) -> int | None:
    values: list[int] = []
    for call in calls:
        value = call.get(field)
        if isinstance(value, int) and not isinstance(value, bool):
            values.append(value)
    if not values:
        return None
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


def _aggregate_cost_status(calls: list[dict[str, Any]]) -> str:
    if not calls:
        return "unknown"
    statuses = {str(call.get("cost_status") or "unknown") for call in calls}
    known_cost_count = sum(
        1
        for call in calls
        if isinstance(call.get("cost_usd"), (int, float))
        and not isinstance(call.get("cost_usd"), bool)
    )
    if statuses == {"known"}:
        return "known"
    if known_cost_count > 0 or "known" in statuses:
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
    input_tokens = (
        _sum_int_field(successful, "input_tokens")
        if complete
        else _sum_available_int_field(successful, "input_tokens")
    )
    output_tokens = (
        _sum_int_field(successful, "output_tokens")
        if complete
        else _sum_available_int_field(successful, "output_tokens")
    )
    total_tokens = (
        _sum_int_field(successful, "total_tokens")
        if complete
        else _sum_available_int_field(successful, "total_tokens")
    )
    cost_usd = _sum_known_costs(llm_calls)
    cost_status = _aggregate_cost_status(llm_calls)

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
