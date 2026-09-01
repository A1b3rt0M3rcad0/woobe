from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.agent.application.interfaces.agent_run_repository import AgentRunRepository
from modules.agent.application.interfaces.project_access_repository import ProjectAccessRepository
from modules.agent.domain.run import AgentRun


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


class ListAgentRunsUseCase:
    def __init__(
        self,
        runs: AgentRunRepository,
        project_access: ProjectAccessRepository,
    ) -> None:
        self._runs = runs
        self._project_access = project_access

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
        return [_summary(run) for run in runs]
