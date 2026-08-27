from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.agent.application.interfaces.agent_run_repository import AgentRunRepository
from modules.agent.application.interfaces.project_access_repository import ProjectAccessRepository
from modules.agent.domain.run import AgentRun
from shared.contracts.errors import NotFoundError


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else None


def _run_detail(run: AgentRun) -> dict[str, Any]:
    result = dict(run.result or {}) if isinstance(run.result, dict) else {}
    usage = dict(run.usage or {}) if isinstance(run.usage, dict) else {}
    result_usage = result.get("usage")
    if not usage and isinstance(result_usage, dict):
        usage = dict(result_usage)

    diagnostics = result.get("diagnostics")
    tool_calls = result.get("tool_calls")
    sources = result.get("sources")
    llm_calls = result.get("llm_calls")

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
        "answer": result.get("answer"),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "parsed_output": result.get("parsed_output"),
        "output_parse_error": result.get("output_parse_error"),
        "usage": usage or None,
        "diagnostics": diagnostics if isinstance(diagnostics, dict) else None,
        "tool_calls": tool_calls if isinstance(tool_calls, list) else [],
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
        return _run_detail(run)

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
        return _run_detail(run)
