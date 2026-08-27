from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from modules.agent.infra.database.run_models import AgentRunModel
from modules.chat_surface.infra.database.models import ChatSurfaceMessageRequestModel
from modules.chat_surface.presentation.routes import _authorized_session, _service
from modules.network.application.service import NetworkApplicationService
from modules.network.infra.database.models import NetworkExecutionModel
from modules.network.presentation.reattach_routes import (
    _durable_state as network_durable_state,
    network_runtime_sse,
)
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


def _network_service(request: Request) -> NetworkApplicationService:
    settings = request.app.state.settings
    return NetworkApplicationService(
        request.app.state.session_factory,
        hard_max_depth=settings.network_max_depth_hard,
        hard_max_invocations=settings.network_max_invocations_hard,
        hard_timeout_seconds=settings.network_timeout_hard_seconds,
    )


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


def _valid_network_run(execution: NetworkExecutionModel | None, authorized) -> bool:
    return bool(
        execution is not None
        and execution.project_id == authorized.binding.project_id
        and execution.network_id == authorized.binding.target_id
        and execution.network_session_id == authorized.binding.session_id
        and execution.network_version_id == authorized.binding.target_release_id
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

    async with request.app.state.session_factory() as session:
        if authorized.binding.target_type == "agent":
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

        if message_request.target_run_id is not None:
            candidate = await session.get(
                NetworkExecutionModel,
                message_request.target_run_id,
            )
            if _valid_network_run(candidate, authorized) and (
                str(candidate.status) in _NETWORK_ACTIVE
                or message_request.status in _MESSAGE_ACTIVE
            ):
                return candidate.id, str(candidate.status)

        candidate = await session.scalar(
            select(NetworkExecutionModel)
            .where(
                NetworkExecutionModel.project_id == authorized.binding.project_id,
                NetworkExecutionModel.network_id == authorized.binding.target_id,
                NetworkExecutionModel.network_session_id == authorized.binding.session_id,
                NetworkExecutionModel.network_version_id
                == authorized.binding.target_release_id,
                NetworkExecutionModel.status.in_(_NETWORK_ACTIVE),
            )
            .order_by(
                NetworkExecutionModel.created_at.desc(),
                NetworkExecutionModel.id.desc(),
            )
            .limit(1)
        )
        if _valid_network_run(candidate, authorized):
            return candidate.id, str(candidate.status)
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

    message_request = await _latest_message_request(request, authorized.binding.id)
    run_id, run_status = await _resolve_run_identity(
        request,
        authorized,
        message_request,
    )

    # Agent Acceptance and ChatSurface admission are separate durable boundaries.
    # A disconnect can also close the old observer before ChatSurface persisted the
    # canonical Run id. Recover identity from the underlying Run bound to this Session.
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
        # Restore the operational gate if the previous observer disconnected after
        # the Run had already been accepted. The Run, not that observer, owns life.
        await _service(request).mark_message(
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
    if message_request is None or run_id is None:
        return {"success": True, "data": None}
    return {
        "success": True,
        "data": {
            "message_request_id": str(message_request.id),
            "run_id": str(run_id),
            "status": run_status or message_request.status,
            "target_type": authorized.binding.target_type,
        },
    }


@router.post("/v1/chat/sessions/{session_id}/active-run/cancel")
async def cancel_chat_active_run(
    session_id: UUID,
    request: Request,
    host_origin: str | None = Header(default=None, alias="X-Woobe-Host-Origin"),
):
    authorized, message_request, run_id, run_status = await _authorized_active_request(
        request,
        session_id,
        host_origin,
        permission="chat:cancel",
        require_stream=False,
    )
    if message_request is None or run_id is None:
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
        state = await EXECUTION_STATE_STORE.get(run_id)
        if state is None:
            if str(run.status) in _AGENT_TERMINAL:
                status = str(run.status)
            else:
                raise ConflictError(
                    "Agent Run has no active runtime state; cancellation cannot be confirmed safely"
                )
        else:
            await EXECUTION_STATE_STORE.request_cancel(run_id)
            status = "cancel_requested"
    else:
        async with request.app.state.session_factory() as session:
            execution = await session.get(NetworkExecutionModel, run_id)
        if not _valid_network_run(execution, authorized):
            raise NotFoundError("Network execution not found")
        await _network_service(request).request_cancellation(
            execution.id,
            execution.project_id,
        )
        status = (
            str(execution.status)
            if str(execution.status) in _NETWORK_TERMINAL
            else "cancel_requested"
        )

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
    if message_request is None:
        raise NotFoundError("ChatSurface Session has no active Run")
    if run_id is None:
        raise ConflictError("ChatSurface Run was accepted but its identity is not ready")

    reader = RuntimeStreamReader(
        EXECUTION_STATE_STORE,
        heartbeat_seconds=request.app.state.settings.network_stream_heartbeat_seconds,
        block_ms=500,
    )

    if authorized.binding.target_type == "agent":

        async def durable_fallback() -> dict | None:
            async with request.app.state.session_factory() as session:
                run = await session.get(AgentRunModel, run_id)
            if not _valid_agent_run(run, authorized):
                raise NotFoundError("Agent Run not found")
            return _agent_state(run)

        formatter = format_sse_frame
        kind = "agent"
        terminal_statuses = _AGENT_TERMINAL
    else:

        async def durable_fallback() -> dict | None:
            async with request.app.state.session_factory() as session:
                execution = await session.get(NetworkExecutionModel, run_id)
            if not _valid_network_run(execution, authorized):
                raise NotFoundError("Network execution not found")
            return network_durable_state(execution)

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
                "sequence": None,
                "realtime_available": False,
                "degraded_reason": "runtime_event_gap",
            }
            yield formatter(RuntimeStreamFrame("run.state", degraded, sequence=None))
        finally:
            # Observer loss leaves the message request active. Only durable terminal
            # state may close it, preserving reload/reattach semantics.
            if terminal_status is not None:
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

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Woobe-Message-Request-ID": str(message_request.id),
            "X-Woobe-Run-ID": str(run_id),
        },
    )
