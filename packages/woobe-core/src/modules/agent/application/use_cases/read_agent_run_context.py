from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.agent.application.interfaces.agent_run_repository import AgentRunRepository
from modules.agent.application.interfaces.project_access_repository import ProjectAccessRepository
from modules.agent.domain.run import AgentRun
from shared.contracts.errors import NotFoundError


_DIAGNOSTIC_KEYS = (
    "schema_version",
    "agent_runtime_latency_ms",
    "total_latency_ms",
    "prepare_latency_ms",
    "llm_work_latency_ms",
    "llm_runtime_latency_ms",
    "tool_wall_latency_ms",
    "tool_work_latency_ms",
    "tool_call_duration_sum_ms",
    "tool_parallelism_ratio",
    "tool_provider_work_ms",
    "tool_runtime_overhead_ms",
    "finalization_work_latency_ms",
    "persistence_latency_ms",
    "other_latency_ms",
    "unaccounted_latency_ms",
    "orchestration_latency_ms",
    "llm_call_count",
    "tool_call_count",
    "successful_tool_calls",
    "failed_tool_calls",
    "usage_complete",
    "cost_status",
    "cost_reason",
    "cost_statuses",
    "pricing_ids",
    "provider_model_id",
    "provider_credential_id",
    "fallback_provider_model_id",
    "fallback_credential_id",
    "execution_context",
    "agent_release_id",
    "agent_release_version",
    "fallback_used",
    "tool_share_percent",
)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else None


def _normalized_diagnostics(
    result: dict[str, Any],
    tool_calls: list[Any],
) -> dict[str, Any] | None:
    raw = result.get("diagnostics")
    diagnostics = dict(raw) if isinstance(raw, dict) else {
        key: result[key]
        for key in _DIAGNOSTIC_KEYS
        if key in result
    }
    if not diagnostics:
        return None

    successful = sum(
        1
        for call in tool_calls
        if isinstance(call, dict)
        and (
            call.get("success") is True
            or str(call.get("status") or "").lower() in {"success", "completed"}
        )
    )
    failed = sum(
        1
        for call in tool_calls
        if isinstance(call, dict)
        and (
            call.get("success") is False
            or str(call.get("status") or "").lower() in {"failed", "error"}
        )
    )
    diagnostics.setdefault("successful_tool_calls", successful)
    diagnostics.setdefault("failed_tool_calls", failed)
    diagnostics.setdefault("tool_call_count", len(tool_calls))
    return diagnostics


def _run_detail(run: AgentRun) -> dict[str, Any]:
    result = dict(run.result or {}) if isinstance(run.result, dict) else {}
    usage = dict(run.usage or {}) if isinstance(run.usage, dict) else {}
    result_usage = result.get("usage")
    if not usage and isinstance(result_usage, dict):
        usage = dict(result_usage)

    tool_calls_raw = result.get("tool_calls")
    tool_calls = tool_calls_raw if isinstance(tool_calls_raw, list) else []
    sources = result.get("sources")
    llm_calls = result.get("llm_calls")
    diagnostics = _normalized_diagnostics(result, tool_calls)

    return {
        "id": str(run.id),
        "project_id": str(run.project_id),
        "agent_id": str(run.agent_id),
        "session_id": str(run.session_id) if run.session_id else None,
        "agent_release_id": str(run.agent_release_id) if run.agent_release_id else None,
        "input_message_id": str(run.input_message_id) if run.input_message_id else None,
        "output_message_id": str(run.output_message_id) if run.output_message_id else None,
        "trace_id": str(run.trace_id),
        "network_execution_id": str(run.network_execution_id) if run.network_execution_id else None,
        "network_invocation_id": str(run.network_invocation_id) if run.network_invocation_id else None,
        "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
        "rerun_of_run_id": str(run.rerun_of_run_id) if run.rerun_of_run_id else None,
        "environment": run.environment,
        "origin": run.origin,
        "status": run.status.value,
        "input_message": run.input_message,
        "answer": result.get("answer") or result.get("output"),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "parsed_output": result.get("parsed_output"),
        "output_parse_error": result.get("output_parse_error"),
        "usage": usage or None,
        "diagnostics": diagnostics,
        "tool_calls": tool_calls,
        "sources": sources if isinstance(sources, list) else [],
        "llm_calls": llm_calls if isinstance(llm_calls, list) else [],
        "failure": result.get("failure") if isinstance(result.get("failure"), dict) else None,
        "failure_code": run.failure_code,
        "failure_detail": run.failure_detail,
        "started_at": _iso(run.started_at),
        "completed_at": _iso(run.completed_at),
        "created_at": _iso(run.created_at),
        "updated_at": _iso(run.updated_at),
    }


class ReadAgentRunContextUseCase:
    def __init__(
        self,
        run_repository: AgentRunRepository,
        project_access_repository: ProjectAccessRepository,
    ) -> None:
        self._runs = run_repository
        self._project_access = project_access_repository

    async def _authorized_run(self, *, run: AgentRun | None, user_id: UUID, not_found: str) -> AgentRun:
        if run is None:
            raise NotFoundError(not_found)
        await self._project_access.require_user_access(
            user_id=user_id,
            project_id=run.project_id,
        )
        return run

    async def _detail(self, run: AgentRun) -> dict[str, Any]:
        detail = _run_detail(run)
        if not detail["answer"] and run.output_message_id is not None:
            detail["answer"] = await self._runs.get_output_message_content(
                run.output_message_id
            )
        return detail

    async def by_run(
        self,
        *,
        run_id: UUID,
        user_id: UUID,
    ) -> list[dict]:
        run = await self._authorized_run(
            run=await self._runs.get_by_id(run_id),
            user_id=user_id,
            not_found="Agent Run not found",
        )
        return await self._runs.list_model_invocations(run.id)

    async def by_trace(
        self,
        *,
        trace_id: UUID,
        user_id: UUID,
    ) -> list[dict]:
        run = await self._authorized_run(
            run=await self._runs.get_by_trace_id(trace_id),
            user_id=user_id,
            not_found="Agent Run not found for Trace",
        )
        return await self._runs.list_model_invocations(run.id)

    async def detail_by_run(
        self,
        *,
        run_id: UUID,
        user_id: UUID,
    ) -> dict:
        run = await self._authorized_run(
            run=await self._runs.get_by_id(run_id),
            user_id=user_id,
            not_found="Agent Run not found",
        )
        return await self._detail(run)

    async def detail_by_trace(
        self,
        *,
        trace_id: UUID,
        user_id: UUID,
    ) -> dict:
        run = await self._authorized_run(
            run=await self._runs.get_by_trace_id(trace_id),
            user_id=user_id,
            not_found="Agent Run not found for Trace",
        )
        return await self._detail(run)
