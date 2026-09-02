from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from modules.agent.entrypoint import (
    AskInput,
    build_agent_chat_surface_history_reader,
    build_agent_chat_surface_runtime,
    build_agent_stream_service,
    commit_safe_stream,
)
from modules.chat_surface.entrypoint import (
    AuthorizedChatSession,
    ChatSurfaceCredentialAuthorizationState,
    ChatSurfaceCredentialReader,
    ChatSurfaceTargetSessionAuthorizer,
    MessageRequestState,
    StreamChatMessageRequest,
    TargetSessionAuthorizationInput,
    begin_chat_surface_message_runtime_composer,
    build_chat_surface_session_authorization_handler,
    latest_chat_surface_message_composer,
    mark_chat_surface_message_runtime_composer,
    normalize_appearance_config,
)
from modules.core.entrypoint import get_chat_surface_credential_composer
from modules.network.entrypoint import (
    NetworkChatSurfaceRun,
    build_network_chat_surface_history_reader,
    build_network_chat_surface_runtime,
)
from shared.contracts.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
)
from shared.presentation.http.request import Request as InternalRequest


CONTROL_PLANE_TEST_SOURCE = "control_plane_test"
_STREAM_PATH = "/chat/sessions/{session_id}/messages:stream"
_SURFACE_PATH = "/chat/sessions/{session_id}/surface"
_MESSAGES_PATH = "/chat/sessions/{session_id}/messages"

_AGENT_TERMINAL = {"completed", "failed", "cancelled", "uncertain"}
_NETWORK_TERMINAL = {"completed", "failed", "cancelled", "timed_out", "uncertain"}
_AGENT_ACTIVE = {"running", "cancel_requested"}
_NETWORK_ACTIVE = {"queued", "running", "cancel_requested"}
_MESSAGE_ACTIVE = {"accepted", "streaming"}

router = APIRouter(tags=["chat-surfaces", "runtime"])


class CoreChatSurfaceCredentialReader(ChatSurfaceCredentialReader):
    async def get(
        self,
        credential_id: UUID,
    ) -> ChatSurfaceCredentialAuthorizationState | None:
        response = await get_chat_surface_credential_composer()(
            InternalRequest(path_params={"credential_id": str(credential_id)})
        )
        data = response.body["data"]
        return (
            ChatSurfaceCredentialAuthorizationState.model_validate(data)
            if data is not None
            else None
        )


class PublicTargetSessionAuthorizer(ChatSurfaceTargetSessionAuthorizer):
    async def is_authorized(
        self,
        input_dto: TargetSessionAuthorizationInput,
    ) -> bool:
        if input_dto.target_type == "agent":
            return await build_agent_chat_surface_runtime().validate_session(
                project_id=input_dto.project_id,
                agent_id=input_dto.target_id,
                session_id=input_dto.session_id,
                agent_release_id=input_dto.target_release_id,
                chat_surface_id=input_dto.chat_surface_id,
            )
        if input_dto.target_type == "network":
            return await build_network_chat_surface_runtime().validate_session(
                project_id=input_dto.project_id,
                network_id=input_dto.target_id,
                network_session_id=input_dto.session_id,
                network_version_id=input_dto.target_release_id,
                chat_surface_id=input_dto.chat_surface_id,
            )
        return False


def _bearer(request: Request) -> str:
    scheme, _, credentials = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not credentials:
        raise AuthenticationError("Bearer authentication required")
    return credentials


def _host_origin(value: str | None) -> str:
    if value is None or not value.strip():
        raise AuthorizationError("X-Woobe-Host-Origin is required")
    return value


async def _authorize_session(
    request: Request,
    session_id: UUID,
    *,
    permission: str,
    host_origin: str | None,
) -> AuthorizedChatSession:
    handler = build_chat_surface_session_authorization_handler(
        CoreChatSurfaceCredentialReader(),
        PublicTargetSessionAuthorizer(),
    )
    response = await handler(
        InternalRequest(
            body={
                "token": _bearer(request),
                "expected_session_id": str(session_id),
                "host_origin": _host_origin(host_origin),
                "permission": permission,
            }
        )
    )
    return AuthorizedChatSession.model_validate(response.body["data"])


async def _begin_message_request(
    *,
    surface_id: UUID,
    session_binding_id: UUID,
    idempotency_key: str,
    metadata: dict | None = None,
) -> tuple[MessageRequestState, bool]:
    handler = begin_chat_surface_message_runtime_composer()
    result = await handler(
        surface_id=surface_id,
        session_binding_id=session_binding_id,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )
    return result.request, result.created


async def _latest_message_request(
    session_binding_id: UUID,
) -> MessageRequestState | None:
    response = await latest_chat_surface_message_composer()(
        InternalRequest(
            path_params={"session_binding_id": str(session_binding_id)},
        )
    )
    data = response.body["data"]
    return MessageRequestState.model_validate(data) if data is not None else None


async def _mark_message_request(
    request_id: UUID,
    *,
    status: str,
    target_run_id: UUID | None = None,
    error_code: str | None = None,
) -> MessageRequestState | None:
    handler = mark_chat_surface_message_runtime_composer()
    return await handler(
        request_id,
        status=status,
        target_run_id=target_run_id,
        error_code=error_code,
    )


async def _agent_stream(
    request: Request,
    *,
    message_request_id: UUID,
    authorized: AuthorizedChatSession,
    payload: StreamChatMessageRequest,
) -> AsyncIterator[str]:
    terminal_status = "failed"
    try:
        await _mark_message_request(message_request_id, status="streaming")
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
        await _mark_message_request(
            message_request_id,
            status=terminal_status,
            error_code="runtime_failed" if terminal_status == "failed" else None,
        )


async def _network_stream(
    request: Request,
    *,
    message_request_id: UUID,
    execution: NetworkChatSurfaceRun,
    authorized: AuthorizedChatSession,
) -> AsyncIterator[str]:
    runtime = build_network_chat_surface_runtime()
    await _mark_message_request(
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
        await _mark_message_request(
            message_request_id,
            status="completed" if succeeded else "failed",
            error_code=None if succeeded else "runtime_failed",
        )
    except Exception:
        await _mark_message_request(
            message_request_id,
            status="failed",
            error_code="runtime_failed",
        )
        raise


@router.get(_SURFACE_PATH)
async def get_public_surface_configuration(
    session_id: UUID,
    request: Request,
    host_origin: str | None = Header(default=None, alias="X-Woobe-Host-Origin"),
):
    authorized = await _authorize_session(
        request,
        session_id,
        permission="chat:history",
        host_origin=host_origin,
    )
    return {
        "success": True,
        "data": {
            "surface_id": authorized.surface.public_id,
            "name": authorized.surface.name,
            "appearance": normalize_appearance_config(
                dict(authorized.surface.appearance_config or {})
            ),
            "protocol_version": 1,
        },
    }


@router.get(_MESSAGES_PATH)
async def list_public_messages(
    session_id: UUID,
    request: Request,
    limit: int = 50,
    cursor: UUID | None = None,
    host_origin: str | None = Header(default=None, alias="X-Woobe-Host-Origin"),
):
    authorized = await _authorize_session(
        request,
        session_id,
        permission="chat:history",
        host_origin=host_origin,
    )
    if authorized.surface.target_type == "agent":
        page = await build_agent_chat_surface_history_reader().list_messages(
            project_id=authorized.surface.project_id,
            agent_id=authorized.surface.target_id,
            session_id=authorized.binding.session_id,
            agent_release_id=authorized.binding.target_release_id,
            chat_surface_id=authorized.surface.id,
            limit=limit,
            cursor=cursor,
        )
    else:
        page = await build_network_chat_surface_history_reader().list_messages(
            project_id=authorized.surface.project_id,
            network_id=authorized.surface.target_id,
            network_session_id=authorized.binding.session_id,
            network_version_id=authorized.binding.target_release_id,
            chat_surface_id=authorized.surface.id,
            limit=limit,
            cursor=cursor,
        )
    return {
        "success": True,
        "data": {
            "items": [
                {
                    "id": str(message.id),
                    "role": message.role,
                    "content": message.content,
                    "data": message.data,
                    "created_at": message.created_at,
                }
                for message in page.items
            ],
            "next_cursor": page.next_cursor,
            "has_next": page.has_next,
        },
    }


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
    authorized = await _authorize_session(
        request,
        session_id,
        permission="chat:send",
        host_origin=host_origin,
    )
    if "chat:stream" not in authorized.claims.permissions:
        raise AuthorizationError("ChatSurface Session token scope is insufficient")

    message_request, created = await _begin_message_request(
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
                await _mark_message_request(
                    message_request.id,
                    status="streaming",
                    target_run_id=execution.id,
                )
            except Exception:
                await _mark_message_request(
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


async def _resolve_run_identity(
    authorized: AuthorizedChatSession,
    message_request: MessageRequestState | None,
):
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
    authorized = await _authorize_session(
        request,
        session_id,
        permission=permission,
        host_origin=host_origin,
    )
    if require_stream and "chat:stream" not in authorized.claims.permissions:
        raise AuthorizationError("ChatSurface Session token scope is insufficient")

    message_request = await _latest_message_request(authorized.binding.id)
    run_id, run_status = await _resolve_run_identity(authorized, message_request)

    if message_request is not None and run_id is None:
        for _ in range(20):
            await asyncio.sleep(0.05)
            message_request = await _latest_message_request(authorized.binding.id)
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
        await _mark_message_request(
            message_request.id,
            status="streaming",
            target_run_id=run_id,
            error_code=None,
        )
        message_request = await _latest_message_request(authorized.binding.id)

    return authorized, message_request, run_id, run_status


@router.get("/chat/sessions/{session_id}/active-run")
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
            "status": run_status
            or (message_request.status if message_request is not None else None),
            "target_type": authorized.binding.target_type,
        },
    }


@router.post("/chat/sessions/{session_id}/active-run/cancel")
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


@router.get("/chat/sessions/{session_id}/active-run/stream")
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
                await _mark_message_request(
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


__all__ = ["router"]
