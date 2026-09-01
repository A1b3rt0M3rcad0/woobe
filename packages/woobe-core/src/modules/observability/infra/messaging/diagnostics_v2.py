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


def _tool_provider_latency(tool: dict[str, Any]) -> float | None:
    direct = _n(tool.get("provider_latency_ms"))
    if direct is not None:
        return direct
    output = tool.get("output")
    if isinstance(output, dict):
        return _n(output.get("provider_latency_ms"))
    return None


def build(payload: dict[str, Any]) -> dict[str, Any]:
    raw_tools = payload.get("tool_calls") or []
    raw_tools = [x for x in raw_tools if isinstance(x, dict)]
    tools = [tool for tool in raw_tools if not _is_delegation_tool(tool)]
    has_internal_delegation = len(tools) != len(raw_tools)

    calls = payload.get("llm_calls") or []
    calls = [x for x in calls if isinstance(x, dict)]

    runtime = _n(
        payload.get("agent_runtime_latency_ms")
        or payload.get("total_latency_ms")
        or payload.get("latency_ms")
    )

    llm_work = _n(
        payload.get("llm_work_latency_ms")
        or payload.get("llm_runtime_latency_ms")
    )
    if llm_work is None:
        llm_work = sum(_n(x.get("latency_ms")) or 0 for x in calls)

    tool_work = _n(
        payload.get("tool_work_latency_ms")
        or payload.get("tool_call_duration_sum_ms")
    )
    if has_internal_delegation or tool_work is None:
        tool_work = sum(_n(x.get("duration_ms")) or 0 for x in tools)

    tool_wall = _n(payload.get("tool_wall_latency_ms"))
    if has_internal_delegation or tool_wall is None:
        # Old traces do not retain enough interval information to reconstruct a
        # parallel wall-clock. The cumulative non-delegation work is the safest
        # deterministic legacy fallback.
        tool_wall = tool_work

    provider_work = _n(payload.get("tool_provider_work_ms"))
    if has_internal_delegation or provider_work is None:
        provider_values = [
            value
            for tool in tools
            if (value := _tool_provider_latency(tool)) is not None
        ]
        provider_work = sum(provider_values) if provider_values else None

    runtime_overhead = _n(payload.get("tool_runtime_overhead_ms"))
    if runtime_overhead is None and provider_work is not None:
        runtime_overhead = max((tool_work or 0) - provider_work, 0)

    prepare = _n(payload.get("prepare_latency_ms"))
    finalization = _n(payload.get("finalization_work_latency_ms"))
    if finalization is None:
        finalization = _n(payload.get("persistence_latency_ms"))

    other = _n(payload.get("other_latency_ms"))
    if other is None and runtime is not None:
        accounted_wall = sum(
            value or 0
            for value in (prepare, llm_work, tool_wall, finalization)
        )
        other = max(runtime - accounted_wall, 0)

    parallelism = _n(payload.get("tool_parallelism_ratio"))
    if parallelism is None and tool_wall and tool_wall > 0:
        parallelism = (tool_work or 0) / tool_wall

    # These fields remain readable for historical traces only. New diagnostics
    # must not infer HTTP latency from arbitrary duration_ms values returned by
    # MCP or custom Tool payloads.
    legacy_http = _n(payload.get("tool_http_latency_ms"))
    legacy_overhead = _n(payload.get("tool_overhead_latency_ms"))
    explicit_orchestration = _n(payload.get("orchestration_latency_ms"))

    return {
        "schema_version": 5,
        "agent_runtime_latency_ms": _r(runtime),
        "llm_work_latency_ms": _r(llm_work),
        "llm_runtime_latency_ms": _r(llm_work),
        "tool_wall_latency_ms": _r(tool_wall),
        "tool_work_latency_ms": _r(tool_work),
        "tool_call_duration_sum_ms": _r(tool_work),
        "tool_parallelism_ratio": _r(parallelism),
        "tool_provider_work_ms": _r(provider_work),
        "tool_runtime_overhead_ms": _r(runtime_overhead),
        "prepare_latency_ms": _r(prepare),
        "finalization_work_latency_ms": _r(finalization),
        "persistence_latency_ms": _r(finalization),
        "other_latency_ms": _r(other),
        "unaccounted_latency_ms": _r(other),
        "orchestration_latency_ms": _r(explicit_orchestration),
        "tool_http_latency_ms": _r(legacy_http),
        "tool_overhead_latency_ms": _r(legacy_overhead),
        "tool_share_percent": (
            round(((tool_wall or 0) / runtime) * 100, 2)
            if runtime
            else None
        ),
        "tool_call_count": len(tools),
        "successful_tool_calls": sum(x.get("success") is True for x in tools),
        "failed_tool_calls": sum(x.get("success") is False for x in tools),
        "llm_call_count": len(calls),
        "input_tokens": payload.get("input_tokens"),
        "output_tokens": payload.get("output_tokens"),
        "total_tokens": payload.get("total_tokens"),
        "usage_complete": bool(payload.get("usage_complete")),
        "cost_usd": payload.get("cost_usd"),
        "cost_status": payload.get("cost_status") or "unknown",
        "source_count": len(payload.get("sources") or []),
        "answer_length": payload.get("answer_length"),
        "fallback_used": bool(payload.get("fallback_used")),
        "structured_output": payload.get("parsed_output") is not None,
        "provider": payload.get("provider"),
        "model": payload.get("model"),
        "provider_model_id": payload.get("provider_model_id"),
        "provider_credential_id": payload.get("provider_credential_id"),
        "fallback_provider_model_id": payload.get("fallback_provider_model_id"),
        "fallback_credential_id": payload.get("fallback_credential_id"),
        "notes": [
            "Tool wall is elapsed wall-clock; Tool work is cumulative and may be larger under parallel execution.",
            "Finalization work measures terminal persistence work before the PostgreSQL commit returns.",
            "Other is the unclassified wall-clock residual and is not labeled orchestration unless explicitly measured.",
        ],
    }
