from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from modules.agent.entrypoint import AskInput, build_agent_stream_service, commit_safe_stream
from modules.chat_surface.presentation.http import legacy_routes as _legacy
from modules.chat_surface.presentation.http.message_lifecycle import (
    begin_message_request,
    mark_message_request,
)
from modules.chat_surface.presentation.http.session_authorization import authorize_session
from modules.chat_surface.presentation.schemas import StreamChatMessageRequest
from modules.network.entrypoint import (
    NetworkChatSurfaceRun,
    build_network_chat_surface_runtime,
)
from shared.contracts.errors import AuthorizationError, ConflictError


CONTROL_PLANE_TEST_SOURCE = "control_plane_test"
_STREAM_PATH = "/v1/chat/sessions/{session_id}/messages:stream"

router = APIRouter(tags=["chat-surfaces"])
for route in _legacy.router.routes:
    if getattr(route, "path", None) != _STREAM_PATH:
        router.routes.append(route)


async def _agent_stream(
    request: Request,
    *,
    message_request_id: UUID,
    authorized,
    payload: StreamChatMessageRequest,
) -> AsyncIterator[str]:
    terminal_status = "failed"
    try:
        await mark_message_request(message_request_id, status="streaming")
        session_source = str(
            (authorized.binding.metadata or {}).get("source") or "chat_surface"
        )
        input_dto = AskInput(
            project_id=authorized.surface.project_id,
            agent_id=authorized.surface.target_id,
            message=payload.message,
            session_id=authorized.binding.session_id,
            tenant_id=str(authorized.surface.id),
            metadata={
                **(payload.metadata or {}),
                "source": (
                    "chat_surface_test"
                    if session_source == CONTROL_PLANE_TEST_SOURCE
                    else "chat_surface"
                ),
                "chat_surface_session_source": session_source,
                "chat_surface_id": str(authorized.surface.id),
                "chat_surface_target_release_id": str(
                    authorized.binding.target_release_id
                ),
                "embed_protocol_version": 1,
                "server_received_at": datetime.now(timezone.utc).isoformat(),
            },
            execution_context="production",
            loaded_release_id=authorized.binding.target_release_id,
        )
        agent_service = build_agent_stream_service()
        stream_failed = False
        async for chunk in commit_safe_stream(agent_service, input_dto, request):
            if "event: error" in chunk or "event: cancelled" in chunk:
                stream_failed = True
            yield chunk
        terminal_status = "failed" if stream_failed else "completed"
    except Exception:
        terminal_status = "failed"
        raise
    finally:
        await mark_message_request(
            message_request_id,
            status=terminal_status,
            error_code="runtime_failed" if terminal_status == "failed" else None,
        )


async def _network_stream(
    request: Request,
    *,
    message_request_id: UUID,
    execution: NetworkChatSurfaceRun,
    authorized,
) -> AsyncIterator[str]:
    runtime = build_network_chat_surface_runtime()
    await mark_message_request(
        message_request_id,
        status="streaming",
        target_run_id=execution.id,
    )
    try:
        async for chunk in runtime.stream(
            run_id=execution.id,
            project_id=authorized.surface.project_id,
            network_id=authorized.surface.target_id,
            network_session_id=authorized.binding.session_id,
            network_version_id=authorized.binding.target_release_id,
            is_disconnected=request.is_disconnected,
        ):
            yield chunk
        finished = await runtime.get(
            run_id=execution.id,
            project_id=authorized.surface.project_id,
            network_id=authorized.surface.target_id,
            network_session_id=authorized.binding.session_id,
            network_version_id=authorized.binding.target_release_id,
        )
        succeeded = finished.status == "completed"
        await mark_message_request(
            message_request_id,
            status="completed" if succeeded else "failed",
            error_code=None if succeeded else "runtime_failed",
        )
    except Exception:
        await mark_message_request(
            message_request_id,
            status="failed",
            error_code="runtime_failed",
        )
        raise


@router.post(_STREAM_PATH)
async def stream_public_message(
    session_id: UUID,
    payload: StreamChatMessageRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    host_origin: str | None = Header(default=None, alias="X-Woobe-Host-Origin"),
):
    del last_event_id
    if idempotency_key is None:
        raise ConflictError("Idempotency-Key is required")
    authorized = await authorize_session(
        request,
        session_id,
        permission="chat:send",
        host_origin=host_origin,
    )
    if "chat:stream" not in authorized.claims.permissions:
        raise AuthorizationError("ChatSurface Session token scope is insufficient")

    message_request, created = await begin_message_request(
        surface_id=authorized.surface.id,
        session_binding_id=authorized.binding.id,
        idempotency_key=idempotency_key,
        metadata=payload.metadata,
    )
    headers = {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "X-Woobe-Message-Request-ID": str(message_request.id),
    }
    if authorized.surface.target_type == "agent":
        if not created:
            raise ConflictError(
                "Agent message request already exists; reload Session history"
            )
        stream = _agent_stream(
            request,
            message_request_id=message_request.id,
            authorized=authorized,
            payload=payload,
        )
    else:
        runtime = build_network_chat_surface_runtime()
        if created:
            try:
                execution = await runtime.submit(
                    network_id=authorized.surface.target_id,
                    project_id=authorized.surface.project_id,
                    network_session_id=authorized.binding.session_id,
                    network_version_id=authorized.binding.target_release_id,
                    message=payload.message,
                    idempotency_key=f"chat:{message_request.id}",
                )
                await mark_message_request(
                    message_request.id,
                    status="streaming",
                    target_run_id=execution.id,
                )
            except Exception:
                await mark_message_request(
                    message_request.id,
                    status="failed",
                    error_code="runtime_failed",
                )
                raise
        elif message_request.target_run_id is not None:
            execution = await runtime.get(
                run_id=message_request.target_run_id,
                project_id=authorized.surface.project_id,
                network_id=authorized.surface.target_id,
                network_session_id=authorized.binding.session_id,
                network_version_id=authorized.binding.target_release_id,
            )
        else:
            raise ConflictError(
                "Network message request is accepted but its execution is not ready"
            )
        headers["X-Network-Execution-ID"] = str(execution.id)
        stream = _network_stream(
            request,
            message_request_id=message_request.id,
            execution=execution,
            authorized=authorized,
        )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers=headers,
    )


def __getattr__(name: str):
    return getattr(_legacy, name)


__all__ = ["router", "stream_public_message"]
