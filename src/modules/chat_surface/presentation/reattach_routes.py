from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from modules.agent.infra.database.run_models import AgentRunModel
from modules.chat_surface.presentation.routes import _authorized_session, _service
from modules.network.infra.database.models import NetworkExecutionModel
from modules.network.presentation.reattach_routes import network_runtime_sse
from shared.composition_resources import EXECUTION_STATE_STORE
from shared.infra.errors import AuthorizationError, ConflictError, NotFoundError
from shared.runtime_reattach import RuntimeStreamFrame, RuntimeStreamGapError, RuntimeStreamReader, format_sse_frame


router = APIRouter(tags=["chat-surfaces", "runtime"])
_AGENT_TERMINAL = {"completed", "failed", "cancelled", "uncertain"}
_NETWORK_TERMINAL = {"completed", "failed", "cancelled", "timed_out", "uncertain"}


def _agent_state(run: AgentRunModel) -> dict:
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


def _network_state(execution: NetworkExecutionModel) -> dict:
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
        "input_message": execution.input_message,
        "failure_code": execution.failure_code,
        "failure_detail": execution.failure_detail,
        "updated_at": (
            execution.completed_at.isoformat()
            if execution.completed_at is not None
            else execution.updated_at.isoformat()
        ),
    }


async def _authorized_active_request(
    request: Request,
    session_id: UUID,
    host_origin: str | None,
):
    authorized = await _authorized_session(
        request,
        session_id,
        permission="chat:history",
        host_origin=host_origin,
    )
    if "chat:stream" not in authorized.claims.permissions:
        raise AuthorizationError("ChatSurface Session token scope is insufficient")

    service = _service(request)
    active = await service.active_message_request(authorized)
    if active is not None and active.target_run_id is None:
        # Agent Acceptance and ChatSurface admission are separate durable boundaries.
        # Give the runtime a short window to expose the canonical Run identity.
        for _ in range(20):
            await asyncio.sleep(0.05)
            active = await service.active_message_request(authorized)
            if active is None or active.target_run_id is not None:
                break
    return authorized, active


@router.get("/v1/chat/sessions/{session_id}/active-run")
async def get_chat_active_run(
    session_id: UUID,
    request: Request,
    host_origin: str | None = Header(default=None, alias="X-Woobe-Host-Origin"),
):
    authorized, active = await _authorized_active_request(
        request,
        session_id,
        host_origin,
    )
    if active is None:
        return {"success": True, "data": None}
    return {
        "success": True,
        "data": {
            "message_request_id": str(active.id),
            "run_id": str(active.target_run_id) if active.target_run_id else None,
            "status": active.status,
            "target_type": authorized.binding.target_type,
        },
    }


@router.get("/v1/chat/sessions/{session_id}/active-run/stream")
async def stream_chat_active_run(
    session_id: UUID,
    request: Request,
    host_origin: str | None = Header(default=None, alias="X-Woobe-Host-Origin"),
) -> StreamingResponse:
    authorized, active = await _authorized_active_request(
        request,
        session_id,
        host_origin,
    )
    if active is None:
        raise NotFoundError("ChatSurface Session has no active Run")
    if active.target_run_id is None:
        raise ConflictError("ChatSurface Run was accepted but its identity is not ready")

    run_id = active.target_run_id
    reader = RuntimeStreamReader(
        EXECUTION_STATE_STORE,
        heartbeat_seconds=request.app.state.settings.network_stream_heartbeat_seconds,
        block_ms=500,
    )

    if authorized.binding.target_type == "agent":
        async def durable_fallback() -> dict | None:
            async with request.app.state.session_factory() as session:
                run = await session.get(AgentRunModel, run_id)
            if (
                run is None
                or run.project_id != authorized.binding.project_id
                or run.agent_id != authorized.binding.target_id
                or run.session_id != authorized.binding.session_id
                or run.agent_release_id != authorized.binding.target_release_id
            ):
                raise NotFoundError("Agent Run not found")
            return _agent_state(run)

        formatter = format_sse_frame
        kind = "agent"
        terminal_statuses = _AGENT_TERMINAL
    else:
        async def durable_fallback() -> dict | None:
            async with request.app.state.session_factory() as session:
                execution = await session.get(NetworkExecutionModel, run_id)
            if (
                execution is None
                or execution.project_id != authorized.binding.project_id
                or execution.network_id != authorized.binding.target_id
                or execution.network_session_id != authorized.binding.session_id
                or execution.network_version_id != authorized.binding.target_release_id
            ):
                raise NotFoundError("Network execution not found")
            return _network_state(execution)

        formatter = lambda frame: network_runtime_sse(frame, run_id)
        kind = "network"
        terminal_statuses = _NETWORK_TERMINAL

    async def generate():
        terminal_status: str | None = None
        try:
            async for frame in reader.stream(
                run_id,
                kind,
                durable_fallback=durable_fallback,
            ):
                if await request.is_disconnected():
                    return
                if frame.event_type == "run.state":
                    status = str(frame.data.get("status") or "")
                    if status in terminal_statuses:
                        terminal_status = status
                elif frame.event_type in {"done", "execution_completed"}:
                    terminal_status = "completed"
                elif frame.event_type in {"cancelled", "execution_cancelled"}:
                    terminal_status = "cancelled"
                elif frame.event_type in {"error", "execution_failed"}:
                    terminal_status = "failed"
                yield formatter(frame)
        except RuntimeStreamGapError:
            durable = await durable_fallback()
            if durable is None:
                raise
            status = str(durable.get("status") or "")
            if status in terminal_statuses:
                terminal_status = status
            degraded = {
                **durable,
                "run_id": str(run_id),
                "kind": kind.upper(),
                "sequence": 0,
                "realtime_available": False,
                "degraded_reason": "runtime_event_gap",
            }
            yield formatter(RuntimeStreamFrame("run.state", degraded, sequence=0))
        finally:
            # Observer loss leaves the message request active. Only durable terminal
            # state may close it, preserving reload/reattach semantics.
            if terminal_status is not None:
                await _service(request).mark_message(
                    active.id,
                    status=(
                        "completed"
                        if terminal_status == "completed"
                        else "cancelled"
                        if terminal_status == "cancelled"
                        else "failed"
                    ),
                    target_run_id=run_id,
                    error_code=(
                        None if terminal_status == "completed" else "runtime_failed"
                    ),
                )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Woobe-Message-Request-ID": str(active.id),
            "X-Woobe-Run-ID": str(run_id),
        },
    )
