from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.infra.database.run_models import AgentRunModel
from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkInvocationModel,
)


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


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _elapsed_ms(started_at: datetime | None, ended_at: datetime | None) -> float | None:
    if started_at is None or ended_at is None:
        return None
    return max((ended_at - started_at).total_seconds() * 1000, 0.0)


def _run_result(run: AgentRunModel) -> dict[str, Any]:
    return run.result if isinstance(run.result, dict) else {}


def _run_usage(run: AgentRunModel) -> dict[str, Any]:
    return run.usage if isinstance(run.usage, dict) else {}


def _run_diagnostics(run: AgentRunModel) -> dict[str, Any]:
    value = _run_result(run).get("diagnostics")
    return value if isinstance(value, dict) else {}


def _run_context_snapshots(run: AgentRunModel) -> list[dict[str, Any]]:
    raw_calls = _run_result(run).get("llm_calls")
    if not isinstance(raw_calls, list):
        return []
    snapshots: list[dict[str, Any]] = []
    for call in raw_calls:
        if not isinstance(call, dict):
            continue
        snapshot = call.get("context_snapshot")
        if isinstance(snapshot, dict):
            snapshots.append(snapshot)
    return snapshots


def _is_delegation_tool(tool: dict[str, Any]) -> bool:
    name = tool.get("tool_name")
    return isinstance(name, str) and name.startswith("delegate_to_")


def _external_tools(run: AgentRunModel) -> list[dict[str, Any]]:
    raw = _run_result(run).get("tool_calls")
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


def _merged_interval_duration_ms(
    intervals: list[tuple[datetime, datetime]],
    *,
    clamp_start: datetime,
    clamp_end: datetime,
) -> float:
    normalized = sorted(
        (
            max(start, clamp_start),
            min(end, clamp_end),
        )
        for start, end in intervals
        if end > clamp_start and start < clamp_end
    )
    normalized = [(start, end) for start, end in normalized if end > start]
    if not normalized:
        return 0.0

    merged_start, merged_end = normalized[0]
    total = 0.0
    for start, end in normalized[1:]:
        if start <= merged_end:
            if end > merged_end:
                merged_end = end
            continue
        total += (merged_end - merged_start).total_seconds() * 1000
        merged_start, merged_end = start, end
    total += (merged_end - merged_start).total_seconds() * 1000
    return max(total, 0.0)


def _agent_work_latency_ms(
    runs: list[AgentRunModel],
    *,
    now: datetime,
) -> tuple[float | None, int]:
    if not runs:
        return 0.0, 0

    intervals_by_run: dict[UUID, tuple[datetime, datetime]] = {}
    for run in runs:
        started_at = run.started_at
        ended_at = run.completed_at
        if ended_at is None and run.status == "running":
            ended_at = now
        if started_at is None or ended_at is None or ended_at < started_at:
            continue
        intervals_by_run[run.id] = (started_at, ended_at)

    if len(intervals_by_run) != len(runs):
        return None, len(intervals_by_run)

    children_by_parent: dict[UUID, list[tuple[datetime, datetime]]] = {}
    for run in runs:
        if run.parent_run_id is None:
            continue
        interval = intervals_by_run.get(run.id)
        if interval is not None:
            children_by_parent.setdefault(run.parent_run_id, []).append(interval)

    total_work_ms = 0.0
    for run in runs:
        started_at, ended_at = intervals_by_run[run.id]
        inclusive_ms = _elapsed_ms(started_at, ended_at) or 0.0
        delegated_ms = _merged_interval_duration_ms(
            children_by_parent.get(run.id, []),
            clamp_start=started_at,
            clamp_end=ended_at,
        )
        total_work_ms += max(inclusive_ms - delegated_ms, 0.0)

    return total_work_ms, len(intervals_by_run)


def _context_overview(
    agent_runs: list[AgentRunModel],
    *,
    llm_call_count: int,
) -> dict[str, Any]:
    snapshot_count = 0
    reported_count = 0
    input_units_total = 0.0
    input_units_known = False
    utilizations: list[float] = []
    source_units: Counter[str] = Counter()
    compaction_saving_units = 0.0
    truncation_count = 0
    budget_unknown_count = 0
    health_warning_count = 0
    raw_candidate_units = 0.0
    selected_raw_units = 0.0
    agent_summaries: dict[str, dict[str, Any]] = {}

    for run in agent_runs:
        snapshots = _run_context_snapshots(run)
        if not snapshots:
            continue
        agent_id = str(getattr(run, "agent_id", "") or "")
        run_id = str(getattr(run, "id", "") or "")
        summary = agent_summaries.setdefault(
            agent_id,
            {
                "agent_id": agent_id,
                "agent_run_count": 0,
                "model_invocation_count": 0,
                "input_units": 0.0,
                "composition_units": 0.0,
                "peak_utilization": None,
                "delegation_units": 0.0,
                "run_ids": [],
            },
        )
        if run_id and run_id not in summary["run_ids"]:
            summary["run_ids"].append(run_id)
            summary["agent_run_count"] += 1

        for snapshot in snapshots:
            snapshot_count += 1
            summary["model_invocation_count"] += 1
            reported = _number(snapshot.get("reported_input_units"))
            estimated = _number(snapshot.get("estimated_input_units"))
            measured = reported if reported is not None else estimated
            if reported is not None:
                reported_count += 1
            if measured is not None:
                input_units_total += measured
                input_units_known = True
                summary["input_units"] += measured

            utilization = _number(snapshot.get("utilization"))
            if utilization is not None:
                utilizations.append(utilization)
                current_peak = _number(summary.get("peak_utilization"))
                if current_peak is None or utilization > current_peak:
                    summary["peak_utilization"] = utilization

            if snapshot.get("usable_input_budget") is None:
                budget_unknown_count += 1

            manifest = snapshot.get("manifest")
            if not isinstance(manifest, dict):
                continue

            health = manifest.get("health")
            if isinstance(health, dict):
                warnings = health.get("warnings")
                if isinstance(warnings, list):
                    health_warning_count += len(warnings)

            metrics = manifest.get("metrics")
            if isinstance(metrics, dict):
                compaction_saving_units += _number(
                    metrics.get("compaction_saving_units")
                ) or 0.0
                truncation_count += int(_number(metrics.get("truncation_count")) or 0)
                raw_candidate_units += _number(metrics.get("raw_candidate_units")) or 0.0
                selected_raw_units += _number(metrics.get("selected_raw_units")) or 0.0

            sources = manifest.get("sources")
            if not isinstance(sources, dict):
                continue
            for source_type, raw_source in sources.items():
                if not isinstance(raw_source, dict):
                    continue
                units = _number(raw_source.get("units"))
                if units is None:
                    continue
                source_units[str(source_type)] += units
                summary["composition_units"] += units
                if str(source_type).upper() == "DELEGATION":
                    summary["delegation_units"] += units

    if snapshot_count == 0:
        telemetry_status = "unknown"
    elif llm_call_count > 0 and snapshot_count >= llm_call_count:
        telemetry_status = "complete"
    else:
        telemetry_status = "partial"

    if snapshot_count == 0:
        input_measurement = "unknown"
    elif reported_count == snapshot_count:
        input_measurement = "reported"
    elif reported_count > 0:
        input_measurement = "mixed"
    else:
        input_measurement = "estimated"

    total_source_units = sum(source_units.values())
    source_breakdown = {
        source_type: {
            "units": _rounded(units),
            "share": (units / total_source_units) if total_source_units > 0 else None,
        }
        for source_type, units in sorted(source_units.items())
    }
    selection_ratio = (
        selected_raw_units / raw_candidate_units
        if raw_candidate_units > 0
        else None
    )

    normalized_agent_summaries = []
    for summary in agent_summaries.values():
        input_units = float(summary["input_units"])
        composition_units = float(summary["composition_units"])
        delegation_units = float(summary["delegation_units"])
        normalized_agent_summaries.append(
            {
                "agent_id": summary["agent_id"],
                "agent_run_count": summary["agent_run_count"],
                "model_invocation_count": summary["model_invocation_count"],
                "input_units": _rounded(input_units),
                "peak_utilization": _rounded(_number(summary["peak_utilization"])),
                "delegation_units": _rounded(delegation_units),
                "delegation_share": (
                    delegation_units / composition_units
                    if composition_units > 0
                    else None
                ),
                "run_ids": list(summary["run_ids"]),
            }
        )
    normalized_agent_summaries.sort(
        key=lambda item: float(item.get("input_units") or 0),
        reverse=True,
    )

    return {
        "telemetry_status": telemetry_status,
        "model_invocation_count": snapshot_count,
        "input_units": _rounded(input_units_total) if input_units_known else None,
        "input_measurement": input_measurement,
        "peak_utilization": _rounded(max(utilizations)) if utilizations else None,
        "median_utilization": _rounded(_median(utilizations)),
        "budget_unknown_count": budget_unknown_count,
        "health_warning_count": health_warning_count,
        "compaction_saving_units": _rounded(compaction_saving_units),
        "truncation_count": truncation_count,
        "selection_ratio": selection_ratio,
        "source_units": source_breakdown,
        "agents": normalized_agent_summaries,
    }


def build_network_run_diagnostics(
    *,
    execution: NetworkExecutionModel,
    invocations: list[NetworkInvocationModel],
    agent_runs: list[AgentRunModel],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Aggregate Network metrics from canonical child AgentRuns."""

    now = now or datetime.now(timezone.utc)
    run_starts = [run.started_at for run in agent_runs if run.started_at is not None]
    network_start = execution.started_at or (min(run_starts) if run_starts else None)
    network_end = execution.completed_at or now
    network_wall_ms = _elapsed_ms(network_start, network_end)
    agent_work_ms, timing_count = _agent_work_latency_ms(agent_runs, now=now)

    llm_values: list[float | None] = []
    tool_work_values: list[float | None] = []
    prepare_values: list[float | None] = []
    persistence_values: list[float | None] = []
    orchestration_values: list[float | None] = []
    input_values: list[float | None] = []
    output_values: list[float | None] = []
    total_values: list[float | None] = []

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

    for run in agent_runs:
        result = _run_result(run)
        usage = _run_usage(run)
        diagnostics = _run_diagnostics(run)
        if diagnostics:
            diagnostic_count += 1

        llm_values.append(
            _number(
                diagnostics.get("llm_work_latency_ms")
                if diagnostics.get("llm_work_latency_ms") is not None
                else diagnostics.get("llm_runtime_latency_ms")
            )
        )
        prepare_values.append(_number(diagnostics.get("prepare_latency_ms")))
        persistence_values.append(
            _number(
                diagnostics.get("finalization_work_latency_ms")
                if diagnostics.get("finalization_work_latency_ms") is not None
                else diagnostics.get("persistence_latency_ms")
            )
        )
        orchestration_values.append(_number(diagnostics.get("orchestration_latency_ms")))

        tools = _external_tools(run)
        # Agent telemetry intentionally measures every provider function call, including
        # internal delegation functions. Network operational Tool Work must not reuse
        # that aggregate or it double-counts child Agent execution as Tool latency.
        operational_tool_work = _sum_known(
            [
                _number(
                    tool.get("duration_ms")
                    if tool.get("duration_ms") is not None
                    else tool.get("latency_ms")
                )
                for tool in tools
            ],
            empty=0.0,
        )
        tool_work_values.append(operational_tool_work)

        input_values.append(
            _number(usage.get("input_tokens"))
            if usage.get("input_tokens") is not None
            else _number(diagnostics.get("input_tokens"))
        )
        output_values.append(
            _number(usage.get("output_tokens"))
            if usage.get("output_tokens") is not None
            else _number(diagnostics.get("output_tokens"))
        )
        total_values.append(
            _number(usage.get("total_tokens"))
            if usage.get("total_tokens") is not None
            else _number(diagnostics.get("total_tokens"))
        )
        if diagnostics.get("usage_complete") is True:
            usage_complete_count += 1

        llm_count = _number(diagnostics.get("llm_call_count"))
        if llm_count is None:
            llm_calls = result.get("llm_calls")
            llm_count = float(len(llm_calls)) if isinstance(llm_calls, list) else 0.0
        llm_call_count += int(llm_count or 0)

        tool_call_count += len(tools)
        successful_tool_calls += sum(tool.get("success") is True for tool in tools)
        failed_tool_calls += sum(tool.get("success") is False for tool in tools)

        raw_sources = result.get("sources")
        sources = _number(diagnostics.get("source_count"))
        if sources is None:
            sources = float(len(raw_sources)) if isinstance(raw_sources, list) else 0.0
        source_count += int(sources or 0)

        if diagnostics.get("fallback_used") is True or result.get("fallback_used") is True:
            fallback_count += 1

        cost_status = diagnostics.get("cost_status") or result.get("cost_status")
        cost = _number(usage.get("cost_usd"))
        if cost is None:
            cost = _number(result.get("cost_usd"))
        if cost is None:
            cost = _number(diagnostics.get("cost_usd"))

        if cost_status == "known" or (cost_status is None and cost is not None):
            known_cost_count += 1
            known_cost_total += cost or 0.0
        elif cost_status == "partial":
            partial_cost_seen = True
            if cost is not None:
                known_cost_total += cost

    agent_count = len(agent_runs)
    delegation_count = sum(run.parent_run_id is not None for run in agent_runs)
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

    timing_complete = timing_count == agent_count
    if agent_count and diagnostic_count == agent_count and timing_complete:
        telemetry_status = "complete"
    elif agent_count or network_wall_ms is not None:
        telemetry_status = "partial"
    else:
        telemetry_status = "unknown"

    context_overview = _context_overview(
        agent_runs,
        llm_call_count=llm_call_count,
    )

    return {
        "schema_version": 1,
        "execution_id": str(execution.id),
        "status": execution.status,
        "network_wall_latency_ms": _rounded(network_wall_ms),
        "agent_work_latency_ms": _rounded(agent_work_ms),
        "llm_runtime_latency_ms": _rounded(
            _sum_known(llm_values, empty=0.0 if not agent_runs else None)
        ),
        "tool_work_latency_ms": _rounded(
            _sum_known(tool_work_values, empty=0.0 if not agent_runs else None)
        ),
        "prepare_latency_ms": _rounded(
            _sum_known(prepare_values, empty=0.0 if not agent_runs else None)
        ),
        "persistence_latency_ms": _rounded(
            _sum_known(persistence_values, empty=0.0 if not agent_runs else None)
        ),
        "orchestration_latency_ms": _rounded(
            _sum_known(orchestration_values, empty=0.0 if not agent_runs else None)
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
            _sum_known(input_values, empty=0.0 if not agent_runs else None)
        ),
        "output_tokens": _rounded(
            _sum_known(output_values, empty=0.0 if not agent_runs else None)
        ),
        "total_tokens": _rounded(
            _sum_known(total_values, empty=0.0 if not agent_runs else None)
        ),
        "usage_complete": bool(agent_count and usage_complete_count == agent_count),
        "cost_usd": cost_usd,
        "cost_status": cost_status,
        "fallback_count": fallback_count,
        "source_count": source_count,
        "telemetry_status": telemetry_status,
        "context": context_overview,
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
        agent_runs = list(
            (
                await self._session.scalars(
                    select(AgentRunModel)
                    .where(
                        AgentRunModel.network_execution_id == execution_id,
                        AgentRunModel.project_id == project_id,
                    )
                    .order_by(AgentRunModel.started_at.asc(), AgentRunModel.created_at.asc())
                )
            ).all()
        )
        return build_network_run_diagnostics(
            execution=execution,
            invocations=invocations,
            agent_runs=agent_runs,
        )
