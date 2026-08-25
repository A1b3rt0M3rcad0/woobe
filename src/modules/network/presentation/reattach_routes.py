from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from modules.network.infra.database.models import NetworkExecutionModel
from shared.composition_resources import EXECUTION_STATE_STORE
from shared.infra.errors import AuthorizationError, NotFoundError
from shared.runtime_reattach import (
    RuntimeStreamFrame,
    RuntimeStreamGapError,
    RuntimeStreamReader,
    format_sse_frame,
)
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


router = APIRouter(prefix="/network", tags=["network", "runtime"])
_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}


def _authorize_project(request: Request, project_id: UUID) -> None:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, ProjectApiPrincipal):
        if principal.project_id != project_id:
            raise AuthorizationError("Runtime key does not belong to this Project")
        return
    if isinstance(principal, AuthenticatedPrincipal):
        return
    raise AuthorizationError("Authentication required")


async def _load_execution(request: Request, execution_id: UUID) -> NetworkExecutionModel:
    async with request.app.state.session_factory() as session:
        execution = await session.get(NetworkExecutionModel, execution_id)
        if execution is None:
            raise NotFoundError("Network execution not found")
        _authorize_project(request, execution.project_id)
        return execution


def _durable_state(execution: NetworkExecutionModel) -> dict:
    return {
        "status": str(execution.status),
        "output": execution.output_message or "",
        "result": (
            {"answer": execution.output_message}
            if execution.output_message is not None
            else None
        ),
        "trace_id": str(execution.root_trace_id) if execution.root_trace_id else None,
        "project_id": str(execution.project_id),
        "network_id": str(execution.network_id),
        "network_session_id": str(execution.network_session_id),
        "failure_code": execution.failure_code,
        "failure_detail": execution.failure_detail,
        "updated_at": (
            execution.completed_at.isoformat()
            if execution.completed_at is not None
            else execution.updated_at.isoformat()
        ),
    }


@router.get("/executions/{execution_id}/stream")
async def reattach_network_execution(
    execution_id: UUID,
    request: Request,
) -> StreamingResponse:
    initial = await _load_execution(request, execution_id)
    reader = RuntimeStreamReader(
        EXECUTION_STATE_STORE,
        heartbeat_seconds=request.app.state.settings.network_stream_heartbeat_seconds,
        block_ms=500,
    )

    async def durable_fallback() -> dict | None:
        latest = await _load_execution(request, execution_id)
        return _durable_state(latest)

    async def generate():
        hot = await EXECUTION_STATE_STORE.get(execution_id)
        if hot is None and str(initial.status) not in _TERMINAL_STATUSES:
            queued = _durable_state(initial)
            queued.update(
                {
                    "run_id": str(execution_id),
                    "kind": "NETWORK",
                    "sequence": 0,
                    "realtime_available": False,
                }
            )
            yield format_sse_frame(RuntimeStreamFrame("run.state", queued, sequence=0))

            # The durable Acceptance may precede worker/Redis initialization. Keep
            # the observer attached to the same Run instead of forcing a new POST.
            while hot is None:
                if await request.is_disconnected():
                    return
                await asyncio.sleep(0.25)
                latest = await _load_execution(request, execution_id)
                if str(latest.status) in _TERMINAL_STATUSES:
                    terminal = _durable_state(latest)
                    terminal.update(
                        {
                            "run_id": str(execution_id),
                            "kind": "NETWORK",
                            "sequence": 0,
                            "realtime_available": False,
                        }
                    )
                    yield format_sse_frame(
                        RuntimeStreamFrame("run.state", terminal, sequence=0)
                    )
                    return
                hot = await EXECUTION_STATE_STORE.get(execution_id)

        try:
            async for frame in reader.stream(
                execution_id,
                "network",
                durable_fallback=durable_fallback,
            ):
                if await request.is_disconnected():
                    return
                yield format_sse_frame(frame)
        except RuntimeStreamGapError:
            latest = await _load_execution(request, execution_id)
            state = _durable_state(latest)
            state.update(
                {
                    "run_id": str(execution_id),
                    "kind": "NETWORK",
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
            "X-Network-Execution-ID": str(execution_id),
        },
    )
