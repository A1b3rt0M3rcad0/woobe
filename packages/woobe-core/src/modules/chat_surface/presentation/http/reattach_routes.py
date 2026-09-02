from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from modules.agent.infra.database.run_models import AgentRunModel
from modules.chat_surface.infra.database.models import ChatSurfaceMessageRequestModel
from modules.chat_surface.presentation.http.routes import _authorized_session, _service
from modules.network.entrypoint import build_network_chat_surface_runtime
from shared.composition_resources import EXECUTION_STATE_STORE
from shared.infra.errors import AuthorizationError, ConflictError, NotFoundError
from shared.runtime_reattach import (
    RuntimeStreamFrame,
    RuntimeStreamGapError,
    RuntimeStreamReader,
    format_sse_frame,
)


router = APIRouter(tags=["chat-surfaces", "runtime"])
_AGENT_TERMINAL = {"completed", "failed", "cancelled", "uncertain"}
_NETWORK_TERMINAL = {"completed", "failed", "cancelled", "timed_out", "uncertain"}
_AGENT_ACTIVE = {"running"}
_NETWORK_ACTIVE = {"queued", "running", "cancel_requested"}
_MESSAGE_ACTIVE = {"accepted", "streaming"}


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


def _valid_agent_run(run: AgentRunModel | None, authorized) -> bool:
    return bool(
        run is not None
        and run.project_id == authorized.binding.project_id
        and run.agent_id == authorized.binding.target_id
        and run.session_id == authorized.binding.session_id
        and run.agent_release_id == authorized.binding.target_release_id
        and run.network_execution_id is None
    )


async def _latest_message_request(request: Request, binding_id: UUID):
    async with request.app.state.session_factory() as session:
        active = await session.scalar(
            select(ChatSurfaceMessageRequestModel)
            .where(
                ChatSurfaceMessageRequestModel.session_binding_id == binding_id,
                ChatSurfaceMessageRequestModel.status.in_(_MESSAGE_ACTIVE),
            )
            .order_by(
                ChatSurfaceMessageRequestModel.created_at.desc(),
                ChatSurfaceMessageRequestModel.id.desc(),
            )
            .limit(1)
        )
        if active is not None:
            return active
        return await session.scalar(
            select(ChatSurfaceMessageRequestModel)
            .where(ChatSurfaceMessageRequestModel.session_binding_id == binding_id)
            .order_by(
                ChatSurfaceMessageRequestModel.created_at.desc(),
                ChatSurfaceMessageRequestModel.id.desc(),
            )
            .limit(1)
        )


async def _resolve_run_identity(request: Request, authorized, message_request):
    if message_request is None:
        return None, None

    if authorized.binding.target_type == "agent":
        async with request.app.state.session_factory() as session:
            if message_request.target_run_id is not None:
                candidate = await session.get(AgentRunModel, message_request.target_run_id)
                if _valid_agent_run(candidate, authorized) and (
                    str(candidate.status) in _AGENT_ACTIVE
                    or message_request.status in _MESSAGE_ACTIVE
                ):
                    return candidate.id, str(candidate.status)

            candidate = await session.scalar(
                select(AgentRunModel)
                .where(
                    AgentRunModel.project_id == authorized.binding.project_id,
                    AgentRunModel.agent_id == authorized.binding.target_id,
                    AgentRunModel.session_id == authorized.binding.session_id,
                    AgentRunModel.agent_release_id == authorized.binding.target_release_id,
                    AgentRunModel.network_execution_id.is_(None),
                    AgentRunModel.status.in_(_AGENT_ACTIVE),
                )
                .order_by(AgentRunModel.created_at.desc(), AgentRunModel.id.desc())
                .limit(1)
            )
        if _valid_agent_run(candidate, authorized):
            return candidate.id, str(candidate.status)
        return None, None

    runtime = build_network_chat_surface_runtime()
    if message_request.target_run_id is not None:
        try:
            candidate = await runtime.get(
                run_id=message_request.target_run_id,
                project_id=authorized.binding.project_id,
                network_id=authorized.binding.target_id,
                network_session_id=authorized.binding.session_id,
                network_version_id=authorized.binding.target_release_id,
            )
        except NotFoundError:
            candidate = None
        if candidate is not None and (
            candidate.status in _NETWORK_ACTIVE
            or message_request.status in _MESSAGE_ACTIVE
        ):
            return candidate.id, candidate.status

    candidate = await runtime.find_active(
        project_id=authorized.binding.project_id,
        network_id=authorized.binding.target_id,
        network_session_id=authorized.binding.session_id,
        network_version_id=authorized.binding.target_release_id,
    )
    if candidate is not None:
        return candidate.id, candidate.status
    return None, None


async def _authorized_active_request(
    request: Request,
    session_id: UUID,
    host_origin: str | None,
    *,
    permission: str = "chat:history",
    require_stream: bool = True,
):
    authorized = await _authorized_session(
        request,
        session_id,
        permission=permission,
        host_origin=host_origin,
    )
    if require_stream and "chat:stream" not in authorized.claims.permissions:
        raise AuthorizationError("ChatSurface Session token scope is insufficient")

    lifecycle = _service(request)
    message_request = await _latest_message_request(request, authorized.binding.id)
    run_id, run_status = await _resolve_run_identity(
        request,
        authorized,
        message_request,
    )

    canonical_resolver = getattr(lifecycle, "_active_run_for_binding", None)
    if run_id is None and callable(canonical_resolver):
        run_id, run_status = await canonical_resolver(authorized.binding)

    if message_request is not None and run_id is None:
        for _ in range(20):
            await asyncio.sleep(0.05)
            message_request = await _latest_message_request(
                request,
                authorized.binding.id,
            )
            run_id, run_status = await _resolve_run_identity(
                request,
                authorized,
                message_request,
            )
            if run_id is not None:
                break

    if (
        message_request is not None
        and run_id is not None
        and run_status in (_AGENT_ACTIVE | _NETWORK_ACTIVE)
        and (
            message_request.status not in _MESSAGE_ACTIVE
            or message_request.target_run_id != run_id
        )
    ):
        await lifecycle.mark_message(
            message_request.id,
            status="streaming",
            target_run_id=run_id,
            error_code=None,
        )
        message_request = await _latest_message_request(
            request,
            authorized.binding.id,
        )

    return authorized, message_request, run_id, run_status


@router.get("/v1/chat/sessions/{session_id}/active-run")
async def get_chat_active_run(
    session_id: UUID,
    request: Request,
    host_origin: str | None = Header(default=None, alias="X-Woobe-Host-Origin"),
):
    authorized, message_request, run_id, run_status = await _authorized_active_request(
        request,
        session_id,
        host_origin,
    )
    if run_id is None:
        return {"success": True, "data": None}
    return {
        "success": True,
        "data": {
            "message_request_id": (
                str(message_request.id) if message_request is not None else None
            ),
            "run_id": str(run_id),
            "status": run_status or (
                message_request.status if message_request is not None else None
            ),
            "target_type": authorized.binding.target_type,
        },
    }


@router.post("/v1/chat/sessions/{session_id}/active-run/cancel")
async def cancel_chat_active_run(
    session_id: UUID,
    request: Request,
    host_origin: str | None = Header(default=None, alias="X-Woobe-Host-Origin"),
):
    authorized, _message_request, run_id, run_status = await _authorized_active_request(
        request,
        session_id,
        host_origin,
        permission="chat:cancel",
        require_stream=False,
    )
    if run_id is None:
        raise NotFoundError("ChatSurface Session has no active Run")

    terminal_statuses = (
        _AGENT_TERMINAL
        if authorized.binding.target_type == "agent"
        else _NETWORK_TERMINAL
    )
    if run_status in terminal_statuses:
        return {
            "success": True,
            "data": {
                "run_id": str(run_id),
                "status": run_status,
                "target_type": authorized.binding.target_type,
            },
        }

    if authorized.binding.target_type == "agent":
        async with request.app.state.session_factory() as session:
            run = await session.get(AgentRunModel, run_id)
        if not _valid_agent_run(run, authorized):
            raise NotFoundError("Agent Run not found")
        try:
            state = await EXECUTION_STATE_STORE.get(run_id)
        except Exception as exc:
            raise ConflictError(
                "Agent Run runtime control state is temporarily unavailable; "
                "cancellation was not requested"
            ) from exc
        if state is None:
            if str(run.status) in _AGENT_TERMINAL:
                status = str(run.status)
            else:
                raise ConflictError(
                    "Agent Run has no active runtime state; cancellation cannot be confirmed safely"
                )
        else:
            try:
                await EXECUTION_STATE_STORE.request_cancel(run_id)
            except Exception as exc:
                raise ConflictError(
                    "Agent Run cancellation request could not be recorded safely"
                ) from exc
            status = "cancel_requested"
    else:
        runtime = build_network_chat_surface_runtime()
        execution = await runtime.cancel(
            run_id=run_id,
            project_id=authorized.binding.project_id,
            network_id=authorized.binding.target_id,
            network_session_id=authorized.binding.session_id,
            network_version_id=authorized.binding.target_release_id,
        )
        status = execution.status

    return {
        "success": True,
        "data": {
            "run_id": str(run_id),
            "status": status,
            "target_type": authorized.binding.target_type,
        },
    }


@router.get("/v1/chat/sessions/{session_id}/active-run/stream")
async def stream_chat_active_run(
    session_id: UUID,
    request: Request,
    host_origin: str | None = Header(default=None, alias="X-Woobe-Host-Origin"),
) -> StreamingResponse:
    authorized, message_request, run_id, _ = await _authorized_active_request(
        request,
        session_id,
        host_origin,
    )
    if run_id is None:
        raise NotFoundError("ChatSurface Session has no active Run")

    if authorized.binding.target_type == "agent":
        reader = RuntimeStreamReader(
            EXECUTION_STATE_STORE,
            heartbeat_seconds=request.app.state.settings.network_stream_heartbeat_seconds,
            block_ms=500,
        )

        async def durable_fallback() -> dict | None:
            async with request.app.state.session_factory() as session:
                run = await session.get(AgentRunModel, run_id)
            if not _valid_agent_run(run, authorized):
                raise NotFoundError("Agent Run not found")
            return _agent_state(run)

        async def generate():
            terminal_status: str | None = None
            try:
                async for frame in reader.stream(
                    run_id,
                    "agent",
                    durable_fallback=durable_fallback,
                ):
                    if await request.is_disconnected():
                        return
                    if frame.event_type == "run.state":
                        status = str(frame.data.get("status") or "")
                        if status in _AGENT_TERMINAL:
                            terminal_status = status
                    elif frame.event_type in {"done", "execution_completed"}:
                        terminal_status = "completed"
                    elif frame.event_type in {"cancelled", "execution_cancelled"}:
                        terminal_status = "cancelled"
                    elif frame.event_type in {"error", "execution_failed"}:
                        terminal_status = "failed"
                    yield format_sse_frame(frame)
            except RuntimeStreamGapError:
                durable = await durable_fallback()
                if durable is None:
                    raise
                status = str(durable.get("status") or "")
                if status in _AGENT_TERMINAL:
                    terminal_status = status
                degraded = {
                    **durable,
                    "run_id": str(run_id),
                    "kind": "AGENT",
                    "sequence": None,
                    "realtime_available": False,
                    "degraded_reason": "runtime_event_gap",
                }
                yield format_sse_frame(
                    RuntimeStreamFrame("run.state", degraded, sequence=None)
                )
            finally:
                if terminal_status is not None and message_request is not None:
                    message_status = (
                        "completed"
                        if terminal_status == "completed"
                        else "cancelled"
                        if terminal_status == "cancelled"
                        else "failed"
                    )
                    await _service(request).mark_message(
                        message_request.id,
                        status=message_status,
                        target_run_id=run_id,
                        error_code=(
                            None
                            if message_status in {"completed", "cancelled"}
                            else "runtime_failed"
                        ),
                    )

    else:
        runtime = build_network_chat_surface_runtime()

        async def generate():
            terminal_status: str | None = None
            try:
                async for chunk in runtime.stream(
                    run_id=run_id,
                    project_id=authorized.binding.project_id,
                    network_id=authorized.binding.target_id,
                    network_session_id=authorized.binding.session_id,
                    network_version_id=authorized.binding.target_release_id,
                    is_disconnected=request.is_disconnected,
                ):
                    yield chunk
                latest = await runtime.get(
                    run_id=run_id,
                    project_id=authorized.binding.project_id,
                    network_id=authorized.binding.target_id,
                    network_session_id=authorized.binding.session_id,
                    network_version_id=authorized.binding.target_release_id,
                )
                if latest.status in _NETWORK_TERMINAL:
                    terminal_status = latest.status
            finally:
                if terminal_status is not None and message_request is not None:
                    message_status = (
                        "completed"
                        if terminal_status == "completed"
                        else "cancelled"
                        if terminal_status == "cancelled"
                        else "failed"
                    )
                    await _service(request).mark_message(
                        message_request.id,
                        status=message_status,
                        target_run_id=run_id,
                        error_code=(
                            None
                            if message_status in {"completed", "cancelled"}
                            else "runtime_failed"
                        ),
                    )

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "X-Woobe-Run-ID": str(run_id),
    }
    if message_request is not None:
        headers["X-Woobe-Message-Request-ID"] = str(message_request.id)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers=headers,
    )
