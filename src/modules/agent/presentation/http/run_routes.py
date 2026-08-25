from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from modules.agent.composition.composers.rerun_agent_run_composer import (
    rerun_agent_run_composer,
)
from modules.agent.infra.database.run_models import AgentRunModel
from shared.composition_resources import EXECUTION_STATE_STORE
from shared.infra.errors import AuthorizationError, ConflictError, NotFoundError
from shared.presentation.http.adapter import request_adapter, response_adapter
from shared.runtime_reattach import (
    RuntimeStreamFrame,
    RuntimeStreamGapError,
    RuntimeStreamReader,
    format_sse_frame,
)
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


router = APIRouter(prefix="/runtime/runs", tags=["runtime", "agent-runs"])
_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}


def _runtime_target(principal: ProjectApiPrincipal) -> tuple[str | None, UUID | None]:
    target_type = principal.target_type
    target_id = principal.target_id
    if target_type is None and principal.agent_id is not None:
        target_type = "agent"
    if target_id is None and principal.agent_id is not None:
        target_id = principal.agent_id
    return target_type, target_id


def _authorize_run(request: FastAPIRequest, run: AgentRunModel) -> None:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, ProjectApiPrincipal):
        if principal.project_id != run.project_id:
            raise AuthorizationError("Runtime key does not belong to this Project")
        if principal.kind == "runtime":
            target_type, target_id = _runtime_target(principal)
            if target_type != "agent" or target_id != run.agent_id:
                raise NotFoundError("Agent Run not found")
            if principal.environment is not None and principal.environment != run.environment:
                raise NotFoundError("Agent Run not found")
        return
    if isinstance(principal, AuthenticatedPrincipal):
        return
    raise AuthorizationError("Authentication required")


async def _load_run(request: FastAPIRequest, run_id: UUID) -> AgentRunModel:
    async with request.app.state.session_factory() as session:
        run = await session.get(AgentRunModel, run_id)
        if run is None:
            raise NotFoundError("Agent Run not found")
        _authorize_run(request, run)
        return run


def _durable_state(run: AgentRunModel) -> dict:
    result = run.result if isinstance(run.result, dict) else None
    answer = result.get("answer") if result else None
    return {
        "status": str(run.status),
        "output": answer or "",
        "result": result,
        "usage": run.usage if isinstance(run.usage, dict) else {},
        "trace_id": str(run.trace_id) if run.trace_id else None,
        "project_id": str(run.project_id),
        "agent_id": str(run.agent_id),
        "session_id": str(run.session_id) if run.session_id else None,
        "updated_at": (
            run.completed_at.isoformat()
            if run.completed_at is not None
            else run.updated_at.isoformat()
        ),
    }


@router.get("/active")
async def active_agent_run(
    request: FastAPIRequest,
    session_id: UUID,
):
    async with request.app.state.session_factory() as session:
        run = await session.scalar(
            select(AgentRunModel)
            .where(
                AgentRunModel.session_id == session_id,
                AgentRunModel.status == "running",
                AgentRunModel.network_execution_id.is_(None),
            )
            .order_by(AgentRunModel.created_at.desc(), AgentRunModel.id.desc())
            .limit(1)
        )
    if run is None:
        return {"success": True, "data": None}
    _authorize_run(request, run)
    return {
        "success": True,
        "data": {
            "run_id": str(run.id),
            "status": str(run.status),
            "session_id": str(run.session_id) if run.session_id else None,
            "agent_id": str(run.agent_id),
            "environment": run.environment,
            "created_at": run.created_at,
        },
    }


@router.get("/{run_id}/stream")
async def attach_agent_run(run_id: UUID, request: FastAPIRequest) -> StreamingResponse:
    run = await _load_run(request, run_id)
    reader = RuntimeStreamReader(EXECUTION_STATE_STORE)

    async def durable_fallback() -> dict | None:
        latest = await _load_run(request, run_id)
        return _durable_state(latest)

    async def generate():
        try:
            async for frame in reader.stream(
                run_id,
                "agent",
                durable_fallback=durable_fallback,
            ):
                if await request.is_disconnected():
                    return
                yield format_sse_frame(frame)
        except RuntimeStreamGapError:
            latest = await _load_run(request, run_id)
            state = _durable_state(latest)
            state.update(
                {
                    "run_id": str(run_id),
                    "kind": "AGENT",
                    "sequence": 0,
                    "realtime_available": False,
                    "degraded_reason": "runtime_event_gap",
                }
            )
            yield format_sse_frame(RuntimeStreamFrame("run.state", state, sequence=0))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Woobe-Run-ID": str(run.id),
        },
    )


@router.post("/{run_id}/cancel", status_code=202)
async def cancel_agent_run(run_id: UUID, request: FastAPIRequest):
    run = await _load_run(request, run_id)
    if str(run.status) in _TERMINAL_STATUSES:
        return {"success": True, "data": {"run_id": str(run_id), "status": str(run.status)}}

    state = await EXECUTION_STATE_STORE.get(run_id)
    if state is None:
        raise ConflictError(
            "Agent Run has no active runtime state; cancellation cannot be confirmed safely"
        )
    await EXECUTION_STATE_STORE.request_cancel(run_id)
    return {
        "success": True,
        "data": {"run_id": str(run_id), "status": "cancel_requested"},
    }


@router.post("/{run_id}/rerun", status_code=201)
async def rerun_agent_run(request: FastAPIRequest):
    response = await request_adapter(request, rerun_agent_run_composer())
    return response_adapter(response)
