from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from modules.chat_surface.application.runtime_gateway import ChatRuntimeTarget
from modules.chat_surface.infra.database.models import ChatSurfaceMessageRequestModel
from modules.chat_surface.presentation.routes import (
    _authorized_session,
    _consume_runtime_stream,
    _runtime_gateway,
    _service,
)
from shared.infra.errors import AuthorizationError, NotFoundError


router = APIRouter(tags=["chat-surfaces", "runtime"])
_TERMINAL = {"completed", "failed", "cancelled", "timed_out", "uncertain"}
_ACTIVE = {"queued", "running", "cancel_requested"}
_MESSAGE_ACTIVE = {"accepted", "streaming"}


def _target(authorized) -> ChatRuntimeTarget:
    return ChatRuntimeTarget(
        project_id=authorized.binding.project_id,
        target_type=authorized.binding.target_type,
        target_id=authorized.binding.target_id,
        target_release_id=authorized.binding.target_release_id,
        session_id=authorized.binding.session_id,
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
    gateway = _runtime_gateway(request)
    identity = await gateway.resolve_run(
        _target(authorized),
        preferred_run_id=(
            message_request.target_run_id if message_request is not None else None
        ),
        created_after=(
            message_request.created_at
            if message_request is not None and message_request.target_run_id is None
            else None
        ),
    )
    if identity is None:
        return None, None
    return identity.run_id, identity.status


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

    if run_id is None and message_request is None:
        identity = await _runtime_gateway(request).resolve_run(_target(authorized))
        if identity is not None:
            run_id, run_status = identity.run_id, identity.status

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
        and run_status in _ACTIVE
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

    if run_status in _TERMINAL:
        status = run_status
    else:
        cancelled = await _runtime_gateway(request).cancel(_target(authorized), run_id)
        status = cancelled.status

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

    prepared = await _runtime_gateway(request).observe(
        _target(authorized),
        run_id,
        request.is_disconnected,
    )
    headers = {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "X-Woobe-Run-ID": str(run_id),
        **(prepared.headers or {}),
    }
    if message_request is not None:
        headers["X-Woobe-Message-Request-ID"] = str(message_request.id)
        stream = _consume_runtime_stream(
            _service(request),
            message_request_id=message_request.id,
            prepared=prepared,
        )
    else:
        async def raw_stream():
            async for chunk in prepared.stream:
                yield chunk.sse
        stream = raw_stream()

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers=headers,
    )
