from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from modules.agent.entrypoint import build_agent_chat_surface_runtime
from modules.chat_surface.presentation.http.message_lifecycle import (
    latest_message_request,
    mark_message_request,
)
from modules.chat_surface.presentation.http.routes import _authorized_session
from modules.network.entrypoint import build_network_chat_surface_runtime
from shared.contracts.errors import AuthorizationError, NotFoundError


router = APIRouter(tags=["chat-surfaces", "runtime"])
_AGENT_TERMINAL = {"completed", "failed", "cancelled", "uncertain"}
_NETWORK_TERMINAL = {"completed", "failed", "cancelled", "timed_out", "uncertain"}
_AGENT_ACTIVE = {"running", "cancel_requested"}
_NETWORK_ACTIVE = {"queued", "running", "cancel_requested"}
_MESSAGE_ACTIVE = {"accepted", "streaming"}


async def _resolve_run_identity(authorized, message_request):
    if authorized.binding.target_type == "agent":
        runtime = build_agent_chat_surface_runtime()
        if message_request is not None and message_request.target_run_id is not None:
            try:
                candidate = await runtime.get(
                    run_id=message_request.target_run_id,
                    project_id=authorized.binding.project_id,
                    agent_id=authorized.binding.target_id,
                    session_id=authorized.binding.session_id,
                    agent_release_id=authorized.binding.target_release_id,
                )
            except NotFoundError:
                candidate = None
            if candidate is not None and (
                candidate.status in _AGENT_ACTIVE
                or message_request.status in _MESSAGE_ACTIVE
            ):
                return candidate.id, candidate.status

        candidate = await runtime.find_active(
            project_id=authorized.binding.project_id,
            agent_id=authorized.binding.target_id,
            session_id=authorized.binding.session_id,
            agent_release_id=authorized.binding.target_release_id,
        )
        if candidate is not None:
            return candidate.id, candidate.status
        return None, None

    runtime = build_network_chat_surface_runtime()
    if message_request is not None and message_request.target_run_id is not None:
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

    message_request = await latest_message_request(authorized.binding.id)
    run_id, run_status = await _resolve_run_identity(authorized, message_request)

    if message_request is not None and run_id is None:
        for _ in range(20):
            await asyncio.sleep(0.05)
            message_request = await latest_message_request(authorized.binding.id)
            run_id, run_status = await _resolve_run_identity(
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
        await mark_message_request(
            message_request.id,
            status="streaming",
            target_run_id=run_id,
            error_code=None,
        )
        message_request = await latest_message_request(authorized.binding.id)

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
        runtime = build_agent_chat_surface_runtime()
        run = await runtime.cancel(
            run_id=run_id,
            project_id=authorized.binding.project_id,
            agent_id=authorized.binding.target_id,
            session_id=authorized.binding.session_id,
            agent_release_id=authorized.binding.target_release_id,
        )
    else:
        runtime = build_network_chat_surface_runtime()
        run = await runtime.cancel(
            run_id=run_id,
            project_id=authorized.binding.project_id,
            network_id=authorized.binding.target_id,
            network_session_id=authorized.binding.session_id,
            network_version_id=authorized.binding.target_release_id,
        )

    return {
        "success": True,
        "data": {
            "run_id": str(run_id),
            "status": run.status,
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
        runtime = build_agent_chat_surface_runtime()
        terminal_statuses = _AGENT_TERMINAL

        async def stream_chunks():
            async for chunk in runtime.stream(
                run_id=run_id,
                project_id=authorized.binding.project_id,
                agent_id=authorized.binding.target_id,
                session_id=authorized.binding.session_id,
                agent_release_id=authorized.binding.target_release_id,
                is_disconnected=request.is_disconnected,
            ):
                yield chunk

        async def latest_status() -> str:
            latest = await runtime.get(
                run_id=run_id,
                project_id=authorized.binding.project_id,
                agent_id=authorized.binding.target_id,
                session_id=authorized.binding.session_id,
                agent_release_id=authorized.binding.target_release_id,
            )
            return latest.status

    else:
        runtime = build_network_chat_surface_runtime()
        terminal_statuses = _NETWORK_TERMINAL

        async def stream_chunks():
            async for chunk in runtime.stream(
                run_id=run_id,
                project_id=authorized.binding.project_id,
                network_id=authorized.binding.target_id,
                network_session_id=authorized.binding.session_id,
                network_version_id=authorized.binding.target_release_id,
                is_disconnected=request.is_disconnected,
            ):
                yield chunk

        async def latest_status() -> str:
            latest = await runtime.get(
                run_id=run_id,
                project_id=authorized.binding.project_id,
                network_id=authorized.binding.target_id,
                network_session_id=authorized.binding.session_id,
                network_version_id=authorized.binding.target_release_id,
            )
            return latest.status

    async def generate():
        terminal_status: str | None = None
        try:
            async for chunk in stream_chunks():
                yield chunk
            status = await latest_status()
            if status in terminal_statuses:
                terminal_status = status
        finally:
            if terminal_status is not None and message_request is not None:
                message_status = (
                    "completed"
                    if terminal_status == "completed"
                    else "cancelled"
                    if terminal_status == "cancelled"
                    else "failed"
                )
                await mark_message_request(
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
