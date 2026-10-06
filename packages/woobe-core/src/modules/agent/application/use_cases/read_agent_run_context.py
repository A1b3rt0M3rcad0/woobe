from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from modules.agent.application.interfaces.agent_run_repository import AgentRunRepository
from modules.agent.application.interfaces.project_access_repository import ProjectAccessRepository
from modules.agent.domain.run import AgentRun
from shared.contracts.errors import NotFoundError
from shared.contracts.run_event_journal import RunEventJournalPort
from shared.contracts.run_event_versions import EVENT_JOURNAL_STORAGE_VERSION

logger = logging.getLogger(__name__)

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

_INVOCATION_DATA_KEYS = (
    "cost_status",
    "cost_reason",
    "pricing_id",
    "upstream_status",
    "upstream_error_code",
    "code",
    "context_fit_status",
    "configured_budget_units",
    "effective_budget_units",
    "mandatory_units",
    "model_capacity_units",
    "reserved_output_units",
    "runtime_reserve_units",
    "provider_called",
)

_TERMINAL_JOURNAL_STATUSES = {
    "completed",
    "failed",
    "cancelled",
    "timed_out",
    "uncertain",
}


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else None


def _payload_iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = str(value).strip()
    return text or None


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


def _journal_model_invocations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    calls = payload.get("llm_calls")
    if not isinstance(calls, list):
        return []

    invocations: list[dict[str, Any]] = []
    for call in calls:
        if not isinstance(call, dict):
            continue
        snapshot = call.get("context_snapshot")
        data = {
            key: call.get(key)
            for key in _INVOCATION_DATA_KEYS
            if call.get(key) is not None
        }
        invocations.append(
            {
                "id": str(call.get("call_id")) if call.get("call_id") else None,
                "call_index": call.get("call_index"),
                "phase": call.get("phase"),
                "provider": call.get("provider"),
                "model": call.get("model"),
                "status": call.get("status"),
                "error": call.get("error"),
                "data": data,
                "latency_ms": call.get("latency_ms"),
                "input_units": call.get("input_tokens"),
                "output_units": call.get("output_tokens"),
                "total_units": call.get("total_tokens"),
                "cost_usd": call.get("cost_usd"),
                "started_at": call.get("started_at"),
                "ended_at": call.get("ended_at"),
                "context_snapshot": dict(snapshot) if isinstance(snapshot, dict) else None,
                "persistence": "agent_run_journal",
            }
        )
    return invocations


def _overlay_terminal_detail(
    detail: dict[str, Any],
    *,
    status: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(detail)
    merged["status"] = status

    answer = payload.get("answer") or payload.get("output")
    if answer is not None:
        merged["answer"] = answer

    for key in ("provider", "model", "parsed_output", "output_parse_error"):
        if key in payload:
            merged[key] = payload.get(key)

    usage = payload.get("usage")
    if isinstance(usage, dict):
        merged["usage"] = dict(usage)

    tool_calls_raw = payload.get("tool_calls")
    if isinstance(tool_calls_raw, list):
        merged["tool_calls"] = list(tool_calls_raw)
    tool_calls = merged.get("tool_calls") if isinstance(merged.get("tool_calls"), list) else []

    sources = payload.get("sources")
    if isinstance(sources, list):
        merged["sources"] = list(sources)

    llm_calls = payload.get("llm_calls")
    if isinstance(llm_calls, list):
        merged["llm_calls"] = list(llm_calls)

    diagnostics = _normalized_diagnostics(payload, tool_calls)
    if diagnostics is not None:
        merged["diagnostics"] = diagnostics

    failure = payload.get("failure")
    if isinstance(failure, dict):
        merged["failure"] = dict(failure)
    if payload.get("failure_code") is not None:
        merged["failure_code"] = str(payload.get("failure_code"))
    if payload.get("error") is not None:
        merged["failure_detail"] = str(payload.get("error"))

    started_at = _payload_iso(payload.get("started_at"))
    completed_at = _payload_iso(payload.get("completed_at"))
    if started_at is not None:
        merged["started_at"] = started_at
    if completed_at is not None:
        merged["completed_at"] = completed_at

    return merged


class ReadAgentRunContextUseCase:
    def __init__(
        self,
        run_repository: AgentRunRepository,
        project_access_repository: ProjectAccessRepository,
        journal: RunEventJournalPort | None = None,
    ) -> None:
        self._runs = run_repository
        self._project_access = project_access_repository
        self._journal = journal

    async def _authorized_run(
        self,
        *,
        run: AgentRun | None,
        user_id: UUID | None,
        control_plane_authorized: bool,
        not_found: str,
    ) -> AgentRun:
        if run is None:
            raise NotFoundError(not_found)
        if not control_plane_authorized:
            if user_id is None:
                raise ValueError("User authentication is required")
            await self._project_access.require_user_access(
                user_id=user_id,
                project_id=run.project_id,
            )
        return run

    async def _durable_terminal_snapshot(
        self,
        run: AgentRun,
    ) -> tuple[str, dict[str, Any]] | None:
        if self._journal is None or run.storage_version != EVENT_JOURNAL_STORAGE_VERSION:
            return None
        try:
            state = await self._journal.get_state(run.id)
            if (
                state is None
                or state.run_kind != "agent"
                or state.storage_version != EVENT_JOURNAL_STORAGE_VERSION
                or state.terminal_sequence is None
                or state.terminal_status not in _TERMINAL_JOURNAL_STATUSES
                or state.terminal_sequence > state.durable_sequence
            ):
                return None

            terminal_sequence = state.terminal_sequence
            events = await self._journal.list_events(
                run.id,
                after_sequence=max(0, terminal_sequence - 1),
                through_sequence=terminal_sequence,
                limit=2,
            )
            event = next(
                (
                    item
                    for item in events
                    if item.sequence == terminal_sequence
                    and item.run_kind == "agent"
                    and item.storage_version == EVENT_JOURNAL_STORAGE_VERSION
                ),
                None,
            )
            if event is None:
                return None
            return str(state.terminal_status), dict(event.payload)
        except Exception as exc:
            # Run inspection must degrade to the PostgreSQL read model when Mongo is
            # temporarily unavailable. Authorization has already been resolved from
            # PostgreSQL before this path is entered.
            logger.warning(
                "Failed to read durable Agent Run terminal snapshot for %s: %s",
                run.id,
                exc,
            )
            return None

    async def _detail(self, run: AgentRun) -> dict[str, Any]:
        detail = _run_detail(run)
        terminal = await self._durable_terminal_snapshot(run)
        if terminal is not None:
            status, payload = terminal
            detail = _overlay_terminal_detail(detail, status=status, payload=payload)

        if not detail["answer"] and run.output_message_id is not None:
            detail["answer"] = await self._runs.get_output_message_content(
                run.output_message_id
            )
        return detail

    async def _model_invocations(self, run: AgentRun) -> list[dict]:
        relational = await self._runs.list_model_invocations(run.id)
        if relational:
            return relational
        terminal = await self._durable_terminal_snapshot(run)
        if terminal is None:
            return []
        _, payload = terminal
        return _journal_model_invocations(payload)

    async def by_run(
        self,
        *,
        run_id: UUID,
        user_id: UUID | None,
        control_plane_authorized: bool = False,
    ) -> list[dict]:
        run = await self._authorized_run(
            run=await self._runs.get_by_id(run_id),
            user_id=user_id,
            control_plane_authorized=control_plane_authorized,
            not_found="Agent Run not found",
        )
        return await self._model_invocations(run)

    async def by_trace(
        self,
        *,
        trace_id: UUID,
        user_id: UUID | None,
        control_plane_authorized: bool = False,
    ) -> list[dict]:
        run = await self._authorized_run(
            run=await self._runs.get_by_trace_id(trace_id),
            user_id=user_id,
            control_plane_authorized=control_plane_authorized,
            not_found="Agent Run not found for Trace",
        )
        return await self._model_invocations(run)

    async def detail_by_run(
        self,
        *,
        run_id: UUID,
        user_id: UUID | None,
        control_plane_authorized: bool = False,
    ) -> dict:
        run = await self._authorized_run(
            run=await self._runs.get_by_id(run_id),
            user_id=user_id,
            control_plane_authorized=control_plane_authorized,
            not_found="Agent Run not found",
        )
        return await self._detail(run)

    async def detail_by_trace(
        self,
        *,
        trace_id: UUID,
        user_id: UUID | None,
        control_plane_authorized: bool = False,
    ) -> dict:
        run = await self._authorized_run(
            run=await self._runs.get_by_trace_id(trace_id),
            user_id=user_id,
            control_plane_authorized=control_plane_authorized,
            not_found="Agent Run not found for Trace",
        )
        return await self._detail(run)
