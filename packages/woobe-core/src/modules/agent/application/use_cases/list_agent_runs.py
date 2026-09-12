from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from modules.agent.application.interfaces.agent_run_repository import AgentRunRepository
from modules.agent.application.interfaces.project_access_repository import ProjectAccessRepository
from modules.agent.domain.run import AgentRun, AgentRunStatus
from shared.contracts.run_event_journal import RunEventJournalPort
from shared.contracts.run_event_versions import EVENT_JOURNAL_STORAGE_VERSION

logger = logging.getLogger(__name__)

_TERMINAL_JOURNAL_STATUSES = {
    "completed",
    "failed",
    "cancelled",
    "timed_out",
    "uncertain",
}


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else None


def _latency_ms(run: AgentRun) -> int | None:
    if run.started_at is None or run.completed_at is None:
        return None
    return max(0, round((run.completed_at - run.started_at).total_seconds() * 1000))


def _summary(run: AgentRun) -> dict[str, Any]:
    result = run.result if isinstance(run.result, dict) else {}
    usage = run.usage if isinstance(run.usage, dict) else {}
    result_usage = result.get("usage")
    if not usage and isinstance(result_usage, dict):
        usage = result_usage

    return {
        "id": str(run.id),
        "trace_id": str(run.trace_id),
        "project_id": str(run.project_id),
        "agent_id": str(run.agent_id),
        "session_id": str(run.session_id) if run.session_id else None,
        "environment": run.environment,
        "origin": run.origin,
        "status": run.status.value,
        "input_message": run.input_message,
        "provider": result.get("provider"),
        "model": result.get("model"),
        "usage": dict(usage) if usage else None,
        "failure_code": run.failure_code,
        "failure_detail": run.failure_detail,
        "latency_ms": _latency_ms(run),
        "started_at": _iso(run.started_at),
        "completed_at": _iso(run.completed_at),
        "created_at": _iso(run.created_at),
        "updated_at": _iso(run.updated_at),
    }


def _number_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0, round(float(value)))
    return None


def _payload_time(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = str(value).strip()
    return text or None


class ListAgentRunsUseCase:
    def __init__(
        self,
        runs: AgentRunRepository,
        project_access: ProjectAccessRepository,
        journal: RunEventJournalPort | None = None,
    ) -> None:
        self._runs = runs
        self._project_access = project_access
        self._journal = journal

    async def _terminal_summary(
        self,
        run: AgentRun,
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        # Avoid one Mongo read per historical row. Only SQL rows that still look
        # active can contradict a terminal durable journal fact.
        if (
            self._journal is None
            or run.status != AgentRunStatus.RUNNING
            or run.storage_version != EVENT_JOURNAL_STORAGE_VERSION
        ):
            return summary

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
                return summary

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
                return summary

            payload = dict(event.payload)
            merged = dict(summary)
            merged["status"] = str(state.terminal_status)
            if payload.get("provider") is not None:
                merged["provider"] = payload.get("provider")
            if payload.get("model") is not None:
                merged["model"] = payload.get("model")
            if isinstance(payload.get("usage"), dict):
                merged["usage"] = dict(payload["usage"])
            latency = _number_or_none(payload.get("latency_ms"))
            if latency is not None:
                merged["latency_ms"] = latency
            started_at = _payload_time(payload.get("started_at"))
            completed_at = _payload_time(payload.get("completed_at"))
            if started_at is not None:
                merged["started_at"] = started_at
            if completed_at is not None:
                merged["completed_at"] = completed_at
            if payload.get("failure_code") is not None:
                merged["failure_code"] = str(payload.get("failure_code"))
            if payload.get("error") is not None:
                merged["failure_detail"] = str(payload.get("error"))
            return merged
        except Exception as exc:
            logger.warning(
                "Failed to reconcile Agent Run list item %s with durable journal: %s",
                run.id,
                exc,
            )
            return summary

    async def execute(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID | None = None,
        environment: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        await self._project_access.require_user_access(
            user_id=user_id,
            project_id=project_id,
        )
        runs = await self._runs.list_direct(
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            environment=environment,
            limit=limit,
        )
        result: list[dict[str, Any]] = []
        for run in runs:
            result.append(await self._terminal_summary(run, _summary(run)))
        return result
