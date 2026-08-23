from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.network.infra.database.models import (
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkInvocationModel,
)
from modules.observability.infra.database.models import TraceModel

_TERMINAL_INVOCATION_EVENTS = {
    "agent_invocation_completed",
    "agent_invocation_failed",
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _rounded(value: float | None) -> int | float | None:
    if value is None:
        return None
    rounded = round(value, 3)
    return int(rounded) if rounded.is_integer() else rounded


def _elapsed_ms(started_at: datetime | None, ended_at: datetime | None) -> float | None:
    if started_at is None or ended_at is None:
        return None
    return max((ended_at - started_at).total_seconds() * 1000, 0.0)


def _trace_data(trace: TraceModel | None) -> dict[str, Any]:
    return trace.data if trace is not None and isinstance(trace.data, dict) else {}


def _diagnostics(trace: TraceModel | None) -> dict[str, Any]:
    data = _trace_data(trace)
    diagnostics = data.get("diagnostics")
    return diagnostics if isinstance(diagnostics, dict) else {}


def _tool_http_latency_ms(tool: dict[str, Any]) -> float | None:
    output = tool.get("output")
    if not isinstance(output, dict):
        return None
    direct = _number(output.get("duration_ms"))
    if direct is not None:
        return direct
    nested = output.get("output")
    if isinstance(nested, dict):
        return _number(nested.get("duration_ms"))
    return None


def _is_delegation_tool(tool: dict[str, Any]) -> bool:
    name = tool.get("tool_name")
    return isinstance(name, str) and name.startswith("delegate_to_")


def _external_tools(
    trace: TraceModel | None,
    completed_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    data = _trace_data(trace)
    raw = data.get("tool_calls")
    if not isinstance(raw, list) and completed_payload is not None:
        raw = completed_payload.get("tool_calls")
    if not isinstance(raw, list):
        return []
    return [
        tool
        for tool in raw
        if isinstance(tool, dict) and not _is_delegation_tool(tool)
    ]


def _sum_known(values: list[float | None], *, empty: float | None = None) -> float | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else empty


def build_network_run_diagnostics(
    *,
    execution: NetworkExecutionModel,
    invocations: list[NetworkInvocationModel],
    events: list[NetworkExecutionEventModel],
    traces_by_id: dict[UUID, TraceModel],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    terminal_execution = execution.completed_at is not None
    network_end = execution.completed_at if terminal_execution else now
    network_wall_ms = _elapsed_ms(execution.started_at, network_end)

    started_at_by_invocation: dict[UUID, datetime] = {}
    ended_at_by_invocation: dict[UUID, datetime] = {}
    completed_payload_by_invocation: dict[UUID, dict[str, Any]] = {}
    for event in events:
        invocation_id = event.invocation_id
        if invocation_id is None:
            continue
        if event.event_type == "agent_invocation_started":
            started_at_by_invocation.setdefault(invocation_id, event.created_at)
        if event.event_type in _TERMINAL_INVOCATION_EVENTS:
            ended_at_by_invocation[invocation_id] = event.created_at
        if event.event_type == "agent_invocation_completed":
            completed_payload_by_invocation[invocation_id] = event.payload or {}

    agent_runtime_values: list[float | None] = []
    llm_values: list[float | None] = []
    prepare_values: list[float | None] = []
    persistence_values: list[float | None] = []
    orchestration_values: list[float | None] = []
    token_input_values: list[float | None] = []
    token_output_values: list[float | None] = []
    token_total_values: list[float | None] = []
    tool_duration_values: list[float] = []
    tool_http_values: list[float] = []

    llm_call_count = 0
    tool_call_count = 0
    successful_tool_calls = 0
    failed_tool_calls = 0
    source_count = 0
    fallback_count = 0
    diagnostic_count = 0
    usage_complete_count = 0
    known_cost_count = 0
    partial_cost_seen = False
    known_cost_total = 0.0

    for invocation in invocations:
        trace = traces_by_id.get(invocation.trace_id) if invocation.trace_id else None
        diagnostics = _diagnostics(trace)
        if diagnostics:
            diagnostic_count += 1

        runtime_ms = _number(diagnostics.get("agent_runtime_latency_ms"))
        if runtime_ms is None and trace is not None:
            runtime_ms = _number(trace.total_latency_ms)
        if runtime_ms is None:
            started_at = started_at_by_invocation.get(invocation.id)
            ended_at = ended_at_by_invocation.get(invocation.id)
            if ended_at is None and invocation.status in {"pending", "running"}:
                ended_at = now
            runtime_ms = _elapsed_ms(started_at, ended_at)
        agent_runtime_values.append(runtime_ms)

        llm_values.append(_number(diagnostics.get("llm_runtime_latency_ms")))
        prepare_values.append(_number(diagnostics.get("prepare_latency_ms")))
        persistence_values.append(_number(diagnostics.get("persistence_latency_ms")))
        orchestration_values.append(_number(diagnostics.get("orchestration_latency_ms")))

        payload = completed_payload_by_invocation.get(invocation.id)
        usage = payload.get("usage") if isinstance(payload, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        token_input_values.append(
            _number(diagnostics.get("input_tokens"))
            if diagnostics.get("input_tokens") is not None
            else _number(usage.get("input_tokens"))
        )
        token_output_values.append(
            _number(diagnostics.get("output_tokens"))
            if diagnostics.get("output_tokens") is not None
            else _number(usage.get("output_tokens"))
        )
        token_total_values.append(
            _number(diagnostics.get("total_tokens"))
            if diagnostics.get("total_tokens") is not None
            else _number(usage.get("total_tokens"))
        )
        if diagnostics.get("usage_complete") is True:
            usage_complete_count += 1

        llm_count = _number(diagnostics.get("llm_call_count"))
        if llm_count is None and trace is not None:
            data = _trace_data(trace)
            llm_calls = data.get("llm_calls")
            llm_count = float(len(llm_calls)) if isinstance(llm_calls, list) else _number(data.get("llm_call_count"))
        llm_call_count += int(llm_count or 0)

        tools = _external_tools(trace, payload)
        tool_call_count += len(tools)
        successful_tool_calls += sum(tool.get("success") is True for tool in tools)
        failed_tool_calls += sum(tool.get("success") is False for tool in tools)
        tool_duration_values.extend(
            duration
            for tool in tools
            if (duration := _number(tool.get("duration_ms") or tool.get("latency_ms")))
            is not None
        )
        tool_http_values.extend(
            duration
            for tool in tools
            if (duration := _tool_http_latency_ms(tool)) is not None
        )

        sources = diagnostics.get("source_count")
        if sources is None and trace is not None:
            raw_sources = _trace_data(trace).get("sources")
            sources = len(raw_sources) if isinstance(raw_sources, list) else 0
        source_count += int(_number(sources) or 0)

        fallback_used = diagnostics.get("fallback_used")
        if fallback_used is True or (trace is not None and trace.fallback_used):
            fallback_count += 1

        cost_status = diagnostics.get("cost_status")
        if not isinstance(cost_status, str) and trace is not None:
            cost_status = _trace_data(trace).get("cost_status")
        cost = _number(diagnostics.get("cost_usd"))
        if cost is None and trace is not None:
            cost = _number(_trace_data(trace).get("cost_usd"))
        if cost is None and trace is not None:
            cost = _number(trace.total_cost_usd)

        if cost_status == "known" or (cost_status is None and cost is not None):
            known_cost_count += 1
            known_cost_total += cost or 0.0
        elif cost_status == "partial":
            partial_cost_seen = True
            if cost is not None:
                known_cost_total += cost

    agent_count = len(invocations)
    delegation_count = sum(
        invocation.parent_invocation_id is not None for invocation in invocations
    )
    children_by_parent = Counter(
        invocation.parent_invocation_id
        for invocation in invocations
        if invocation.parent_invocation_id is not None
    )
    max_fan_out = max(children_by_parent.values(), default=0)
    max_depth = max((invocation.depth for invocation in invocations), default=-1) + 1

    if agent_count and known_cost_count == agent_count and not partial_cost_seen:
        cost_status = "known"
        cost_usd: float | None = known_cost_total
    elif known_cost_count or partial_cost_seen:
        cost_status = "partial"
        cost_usd = known_cost_total
    else:
        cost_status = "unknown"
        cost_usd = None

    if agent_count and diagnostic_count == agent_count:
        telemetry_status = "complete"
    elif diagnostic_count or any(value is not None for value in agent_runtime_values):
        telemetry_status = "partial"
    else:
        telemetry_status = "unknown"

    return {
        "schema_version": 1,
        "execution_id": str(execution.id),
        "status": execution.status,
        "network_wall_latency_ms": _rounded(network_wall_ms),
        "agent_work_latency_ms": _rounded(
            _sum_known(agent_runtime_values, empty=0.0 if not invocations else None)
        ),
        "llm_runtime_latency_ms": _rounded(
            _sum_known(llm_values, empty=0.0 if not invocations else None)
        ),
        "tool_runtime_latency_ms": _rounded(sum(tool_duration_values)),
        "tool_http_latency_ms": _rounded(sum(tool_http_values)),
        "prepare_latency_ms": _rounded(
            _sum_known(prepare_values, empty=0.0 if not invocations else None)
        ),
        "persistence_latency_ms": _rounded(
            _sum_known(persistence_values, empty=0.0 if not invocations else None)
        ),
        "orchestration_latency_ms": _rounded(
            _sum_known(orchestration_values, empty=0.0 if not invocations else None)
        ),
        "agent_run_count": agent_count,
        "delegation_count": delegation_count,
        "max_depth": max_depth,
        "max_fan_out": max_fan_out,
        "llm_call_count": llm_call_count,
        "tool_call_count": tool_call_count,
        "successful_tool_calls": successful_tool_calls,
        "failed_tool_calls": failed_tool_calls,
        "input_tokens": _rounded(
            _sum_known(token_input_values, empty=0.0 if not invocations else None)
        ),
        "output_tokens": _rounded(
            _sum_known(token_output_values, empty=0.0 if not invocations else None)
        ),
        "total_tokens": _rounded(
            _sum_known(token_total_values, empty=0.0 if not invocations else None)
        ),
        "usage_complete": bool(agent_count and usage_complete_count == agent_count),
        "cost_usd": _rounded(cost_usd),
        "cost_status": cost_status,
        "fallback_count": fallback_count,
        "source_count": source_count,
        "telemetry_status": telemetry_status,
    }


class NetworkRunDiagnosticsReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        execution_id: UUID,
        project_id: UUID,
    ) -> dict[str, Any] | None:
        execution = await self._session.scalar(
            select(NetworkExecutionModel).where(
                NetworkExecutionModel.id == execution_id,
                NetworkExecutionModel.project_id == project_id,
            )
        )
        if execution is None:
            return None

        invocations = list(
            (
                await self._session.scalars(
                    select(NetworkInvocationModel)
                    .where(NetworkInvocationModel.network_execution_id == execution_id)
                    .order_by(NetworkInvocationModel.created_at.asc())
                )
            ).all()
        )
        events = list(
            (
                await self._session.scalars(
                    select(NetworkExecutionEventModel)
                    .where(NetworkExecutionEventModel.network_execution_id == execution_id)
                    .order_by(NetworkExecutionEventModel.sequence.asc())
                )
            ).all()
        )

        trace_ids = {
            invocation.trace_id
            for invocation in invocations
            if invocation.trace_id is not None
        }
        traces_by_id: dict[UUID, TraceModel] = {}
        if trace_ids:
            traces = list(
                (
                    await self._session.scalars(
                        select(TraceModel).where(
                            TraceModel.id.in_(trace_ids),
                            TraceModel.project_id == project_id,
                        )
                    )
                ).all()
            )
            traces_by_id = {trace.id: trace for trace in traces}

        return build_network_run_diagnostics(
            execution=execution,
            invocations=invocations,
            events=events,
            traces_by_id=traces_by_id,
        )
