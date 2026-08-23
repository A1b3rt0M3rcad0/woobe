from typing import Any


def _n(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _r(value: float | None):
    if value is None:
        return None
    value = round(value, 3)
    return int(value) if value.is_integer() else value


def _is_delegation_tool(tool: dict[str, Any]) -> bool:
    name = tool.get("tool_name")
    return isinstance(name, str) and name.startswith("delegate_to_")


def build(payload: dict[str, Any]) -> dict[str, Any]:
    raw_tools = payload.get("tool_calls") or []
    raw_tools = [x for x in raw_tools if isinstance(x, dict)]
    tools = [tool for tool in raw_tools if not _is_delegation_tool(tool)]
    has_internal_delegation = len(tools) != len(raw_tools)

    calls = payload.get("llm_calls") or []
    calls = [x for x in calls if isinstance(x, dict)]
    runtime = _n(payload.get("total_latency_ms") or payload.get("latency_ms"))
    llm = _n(payload.get("llm_runtime_latency_ms"))
    if llm is None:
        llm = sum(_n(x.get("latency_ms")) or 0 for x in calls)

    summed = _n(payload.get("tool_call_duration_sum_ms"))
    if has_internal_delegation or summed is None:
        summed = sum(_n(x.get("duration_ms")) or 0 for x in tools)

    wall = _n(payload.get("tool_wall_latency_ms"))
    if has_internal_delegation or wall is None:
        wall = summed

    http = _n(payload.get("tool_http_latency_ms")) or 0
    prepare = _n(payload.get("prepare_latency_ms"))
    persist = _n(payload.get("persistence_latency_ms"))
    orchestration = _n(payload.get("orchestration_latency_ms"))
    accounted = sum(x or 0 for x in (llm, wall, prepare, persist, orchestration))
    unaccounted = max((runtime or 0) - accounted, 0) if runtime is not None else None
    return {
        "schema_version": 2,
        "agent_runtime_latency_ms": _r(runtime),
        "llm_runtime_latency_ms": _r(llm),
        "tool_wall_latency_ms": _r(wall),
        "tool_call_duration_sum_ms": _r(summed),
        # Kept only for compatibility with existing persisted diagnostics.
        # Generic UI and aggregation must use Tool wall / Tool work instead.
        "tool_http_latency_ms": _r(http),
        "tool_overhead_latency_ms": _r(max((summed or 0) - http, 0)),
        "prepare_latency_ms": _r(prepare),
        "persistence_latency_ms": _r(persist),
        "orchestration_latency_ms": _r(orchestration),
        "unaccounted_latency_ms": _r(unaccounted),
        "tool_share_percent": round(((wall or 0) / runtime) * 100, 2) if runtime else None,
        "tool_call_count": len(tools),
        "successful_tool_calls": sum(x.get("success") is True for x in tools),
        "failed_tool_calls": sum(x.get("success") is False for x in tools),
        "llm_call_count": len(calls),
        "input_tokens": payload.get("input_tokens"),
        "output_tokens": payload.get("output_tokens"),
        "total_tokens": payload.get("total_tokens"),
        "usage_complete": bool(payload.get("usage_complete")),
        "cost_status": payload.get("cost_status") or "unknown",
        "source_count": len(payload.get("sources") or []),
        "answer_length": payload.get("answer_length"),
        "fallback_used": bool(payload.get("fallback_used")),
        "structured_output": payload.get("parsed_output") is not None,
        "provider": payload.get("provider"),
        "model": payload.get("model"),
    }
