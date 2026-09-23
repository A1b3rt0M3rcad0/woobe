from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from modules.chat_surface.entrypoint import (
    ChatRuntimeGateway,
    ChatRuntimeRequest,
    PreparedChatRuntime,
)
from modules.chat_surface.entrypoint import (
    CONTROL_PLANE_TEST_SOURCE,
    ControlPlaneChatSurfaceService,
    build_chat_surface_service,
)
from modules.chat_surface.entrypoint import (
    CreateChatSurfaceRequest,
    CreateSurfaceAccessKeyRequest,
    CreateSurfaceSessionRequest,
    IssueSessionTokenRequest,
    StreamChatMessageRequest,
    UpdateChatSurfaceRequest,
)
from modules.chat_surface.entrypoint import surface_payload
from shared.infra.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
)
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal
from shared.security.rate_limit import SlidingWindowRateLimiter


router = APIRouter(tags=["chat-surfaces"])


def _service(request: Request) -> ControlPlaneChatSurfaceService:
    settings = request.app.state.settings
    if not settings.chat_surface_enabled:
        raise NotFoundError("ChatSurface is not enabled")
    return build_chat_surface_service(_runtime_gateway(request))


def _runtime_gateway(request: Request) -> ChatRuntimeGateway:
    gateway = getattr(request.app.state, "chat_surface_runtime_gateway", None)
    if gateway is None:
        raise RuntimeError("ChatSurface runtime gateway is not configured")
    return gateway


def _management_actor(
    request: Request,
) -> tuple[UUID, UUID | None, UUID | None]:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, AuthenticatedPrincipal):
        return principal.user_id, principal.user_id, None
    if isinstance(principal, ControlPlanePrincipal):
        return principal.api_key_id, None, principal.api_key_id
    raise AuthorizationError("Management authentication required")


def _bearer(request: Request) -> str:
    scheme, _, credentials = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not credentials:
        raise AuthenticationError("Bearer authentication required")
    return credentials


def _host_origin(value: str | None) -> str:
    if value is None or not value.strip():
        raise AuthorizationError("X-Woobe-Host-Origin is required")
    return value


def _key_payload(
    api_key,
    *,
    secret: str | None = None,
    display_prefix: str | None = None,
):
    payload = {
        "id": str(api_key.id),
        "credential_id": str(api_key.credential_id),
        "chat_surface_id": str(api_key.chat_surface_id),
        "name": api_key.name,
        "description": api_key.description,
        "prefix": display_prefix or api_key.key_prefix,
        "scopes": list(api_key.scopes or []),
        "status": api_key.status,
        "last_used_at": api_key.last_used_at,
        "expires_at": api_key.expires_at,
        "created_at": api_key.created_at,
    }
    if secret is not None:
        payload["access_key"] = secret
    return payload


def _binding_payload(binding) -> dict:
    return {
        "id": str(binding.id),
        "chat_surface_id": str(binding.chat_surface_id),
        "session_id": str(binding.session_id),
        "target_type": binding.target_type,
        "target_id": str(binding.target_id),
        "target_release_id": str(binding.target_release_id),
        "external_reference": binding.external_reference,
        "status": binding.status,
        "created_at": binding.created_at,
        "updated_at": binding.updated_at,
    }


@router.post("/chat-surfaces/projects/{project_id}", status_code=201)
async def create_surface(
    project_id: UUID,
    payload: CreateChatSurfaceRequest,
    request: Request,
):
    surface = await _service(request).create_surface(
        project_id=project_id,
        actor_id=_management_actor(request)[0],
        payload=payload,
    )
    return {"success": True, "data": surface_payload(surface)}


@router.get("/chat-surfaces/projects/{project_id}")
async def list_surfaces(project_id: UUID, request: Request):
    _management_actor(request)[0]
    surfaces = await _service(request).list_surfaces(project_id)
    return {"success": True, "data": [surface_payload(item) for item in surfaces]}


@router.get("/chat-surfaces/{surface_id}")
async def get_surface(surface_id: UUID, request: Request):
    _management_actor(request)[0]
    surface = await _service(request).get_surface(surface_id)
    return {"success": True, "data": surface_payload(surface)}


@router.patch("/chat-surfaces/{surface_id}")
async def update_surface(
    surface_id: UUID,
    payload: UpdateChatSurfaceRequest,
    request: Request,
):
    _management_actor(request)[0]
    surface = await _service(request).update_surface(surface_id, payload)
    return {"success": True, "data": surface_payload(surface)}


@router.post("/chat-surfaces/{surface_id}/release")
async def refresh_surface_release(surface_id: UUID, request: Request):
    _management_actor(request)[0]
    surface = await _service(request).refresh_target_release(surface_id)
    return {"success": True, "data": surface_payload(surface)}


async def _set_surface_status(surface_id: UUID, request: Request, status: str):
    _management_actor(request)[0]
    surface = await _service(request).set_status(surface_id, status)
    return {"success": True, "data": surface_payload(surface)}


@router.post("/chat-surfaces/{surface_id}/activate")
async def activate_surface(surface_id: UUID, request: Request):
    return await _set_surface_status(surface_id, request, "active")


@router.post("/chat-surfaces/{surface_id}/disable")
async def disable_surface(surface_id: UUID, request: Request):
    return await _set_surface_status(surface_id, request, "disabled")


@router.post("/chat-surfaces/{surface_id}/archive")
async def archive_surface(surface_id: UUID, request: Request):
    return await _set_surface_status(surface_id, request, "archived")


@router.post("/chat-surfaces/{surface_id}/access-keys", status_code=201)
async def create_access_key(
    surface_id: UUID,
    payload: CreateSurfaceAccessKeyRequest,
    request: Request,
):
    _, actor_user_id, actor_control_key_id = _management_actor(request)
    api_key, secret, display_prefix = await _service(request).create_access_key(
        surface_id,
        actor_user_id=actor_user_id,
        actor_control_key_id=actor_control_key_id,
        payload=payload,
    )
    return {
        "success": True,
        "data": _key_payload(
            api_key,
            secret=secret,
            display_prefix=display_prefix,
        ),
    }


@router.get("/chat-surfaces/{surface_id}/access-keys")
async def list_access_keys(surface_id: UUID, request: Request):
    _management_actor(request)[0]
    keys = await _service(request).list_access_keys(surface_id)
    return {"success": True, "data": [_key_payload(item) for item in keys]}


@router.post(
    "/chat-surfaces/{surface_id}/access-keys/{api_key_id}/rotate",
    status_code=201,
)
async def rotate_access_key(
    surface_id: UUID,
    api_key_id: UUID,
    request: Request,
):
    _, actor_user_id, actor_control_key_id = _management_actor(request)
    api_key, secret, display_prefix = await _service(request).rotate_access_key(
        surface_id,
        api_key_id,
        actor_user_id=actor_user_id,
        actor_control_key_id=actor_control_key_id,
    )
    return {
        "success": True,
        "data": _key_payload(
            api_key,
            secret=secret,
            display_prefix=display_prefix,
        ),
    }


@router.post("/chat-surfaces/{surface_id}/access-keys/{api_key_id}/revoke")
async def revoke_access_key(
    surface_id: UUID,
    api_key_id: UUID,
    request: Request,
):
    _management_actor(request)[0]
    api_key = await _service(request).revoke_access_key(surface_id, api_key_id)
    return {"success": True, "data": _key_payload(api_key)}


@router.get("/chat-surfaces/{surface_id}/sessions")
async def list_surface_sessions(
    surface_id: UUID,
    request: Request,
    limit: int = 50,
):
    _management_actor(request)[0]
    bindings = await _service(request).list_sessions(surface_id, limit=limit)
    return {"success": True, "data": [_binding_payload(item) for item in bindings]}


@router.get("/chat-surfaces/{surface_id}/activity")
async def get_surface_activity(surface_id: UUID, request: Request):
    _management_actor(request)[0]
    activity = await _service(request).surface_activity(surface_id)
    return {"success": True, "data": activity}


@router.post("/chat-surfaces/{surface_id}/test-sessions", status_code=201)
async def create_test_session(
    surface_id: UUID,
    request: Request,
    origin: str | None = Header(default=None, alias="Origin"),
):
    if origin is None or not origin.strip():
        raise AuthorizationError("Control Plane Origin header is required")
    token, binding, surface = await _service(request).create_test_session(
        surface_id=surface_id,
        actor_id=_management_actor(request)[0],
        origin=origin,
    )
    return {
        "success": True,
        "data": {
            "session_id": str(binding.session_id),
            "target_release_id": str(binding.target_release_id),
            "session_token": token,
            "expires_in": surface.session_token_ttl_seconds,
            "source": CONTROL_PLANE_TEST_SOURCE,
        },
    }


async def _surface_access(
    public_id: str,
    request: Request,
):
    return await _service(request).authenticate_access_key(
        public_id=public_id,
        credentials=_bearer(request),
    )


async def _consume_access_key_rate(
    request: Request,
    *,
    credential_id: UUID,
    namespace: str,
    limit: int,
) -> None:
    del request
    await SlidingWindowRateLimiter(
        namespace=namespace,
        limit=limit,
        window_seconds=60,
        message="ChatSurface Access Key rate limit exceeded",
    ).consume(str(credential_id))


@router.post("/v1/chat-surfaces/{public_id}/sessions", status_code=201)
async def create_public_session(
    public_id: str,
    payload: CreateSurfaceSessionRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if idempotency_key is None:
        raise ConflictError("Idempotency-Key is required")
    surface, credential = await _surface_access(public_id, request)
    await _consume_access_key_rate(
        request,
        credential_id=credential.api_key_id,
        namespace="chat_surface_session_create",
        limit=request.app.state.settings.chat_surface_session_create_rate_limit,
    )
    binding = await _service(request).create_session(
        surface=surface,
        credential=credential,
        idempotency_key=idempotency_key,
        payload=payload,
    )
    return {"success": True, "data": _binding_payload(binding)}


@router.post(
    "/v1/chat-surfaces/{public_id}/sessions/{session_id}/tokens",
    status_code=201,
)
async def issue_public_session_token(
    public_id: str,
    session_id: UUID,
    payload: IssueSessionTokenRequest,
    request: Request,
):
    surface, credential = await _surface_access(public_id, request)
    await _consume_access_key_rate(
        request,
        credential_id=credential.api_key_id,
        namespace="chat_surface_token_issue",
        limit=request.app.state.settings.chat_surface_token_issue_rate_limit,
    )
    token, binding = await _service(request).issue_session_token(
        surface=surface,
        credential=credential,
        session_id=session_id,
        origin=payload.origin,
    )
    return {
        "success": True,
        "data": {
            "session_id": str(binding.session_id),
            "target_release_id": str(binding.target_release_id),
            "session_token": token,
            "expires_in": surface.session_token_ttl_seconds,
        },
    }


@router.post("/v1/chat-surfaces/{public_id}/sessions/{session_id}/archive")
async def archive_public_session(
    public_id: str,
    session_id: UUID,
    request: Request,
):
    surface, credential = await _surface_access(public_id, request)
    binding = await _service(request).archive_session(
        surface=surface,
        credential=credential,
        session_id=session_id,
    )
    return {"success": True, "data": _binding_payload(binding)}


async def _authorized_session(
    request: Request,
    session_id: UUID,
    *,
    permission: str,
    host_origin: str | None,
):
    return await _service(request).authorize_session_token(
        _bearer(request),
        expected_session_id=session_id,
        host_origin=_host_origin(host_origin),
        permission=permission,
    )


@router.get("/v1/chat/sessions/{session_id}/surface")
async def get_public_surface_configuration(
    session_id: UUID,
    request: Request,
    host_origin: str | None = Header(default=None, alias="X-Woobe-Host-Origin"),
):
    authorized = await _authorized_session(
        request,
        session_id,
        permission="chat:history",
        host_origin=host_origin,
    )
    return {
        "success": True,
        "data": await _service(request).embed_configuration(authorized),
    }


@router.get("/v1/chat/sessions/{session_id}/messages")
async def list_public_messages(
    session_id: UUID,
    request: Request,
    limit: int = 50,
    cursor: UUID | None = None,
    host_origin: str | None = Header(default=None, alias="X-Woobe-Host-Origin"),
):
    authorized = await _authorized_session(
        request,
        session_id,
        permission="chat:history",
        host_origin=host_origin,
    )
    data = await _service(request).list_messages(
        authorized,
        limit=limit,
        cursor=cursor,
    )
    return {"success": True, "data": data}


async def _consume_runtime_stream(
    service: ControlPlaneChatSurfaceService,
    *,
    message_request_id: UUID,
    prepared: PreparedChatRuntime,
) -> AsyncIterator[str]:
    current_run_id = prepared.run_id
    await service.mark_message(
        message_request_id,
        status="streaming",
        target_run_id=current_run_id,
        error_code=None,
    )

    terminalized = False
    async for chunk in prepared.stream:
        if chunk.run_id is not None and chunk.run_id != current_run_id:
            current_run_id = chunk.run_id
            await service.mark_message(
                message_request_id,
                status="streaming",
                target_run_id=current_run_id,
                error_code=None,
            )

        if chunk.terminal_status is not None and not terminalized:
            message_status = (
                "completed"
                if chunk.terminal_status == "completed"
                else "cancelled"
                if chunk.terminal_status == "cancelled"
                else "failed"
            )
            await service.mark_message(
                message_request_id,
                status=message_status,
                target_run_id=current_run_id,
                error_code=(
                    None
                    if message_status in {"completed", "cancelled"}
                    else "runtime_failed"
                ),
            )
            terminalized = True

        yield chunk.sse


@router.post("/v1/chat/sessions/{session_id}/messages:stream")
async def stream_public_message(
    session_id: UUID,
    payload: StreamChatMessageRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    host_origin: str | None = Header(default=None, alias="X-Woobe-Host-Origin"),
):
    if idempotency_key is None:
        raise ConflictError("Idempotency-Key is required")
    authorized = await _authorized_session(
        request,
        session_id,
        permission="chat:send",
        host_origin=host_origin,
    )
    if "chat:stream" not in authorized.claims.permissions:
        raise AuthorizationError("ChatSurface Session token scope is insufficient")

    service = _service(request)
    message_request, created = await service.begin_message(
        authorized,
        idempotency_key,
        metadata=payload.metadata,
    )
    session_source = str(
        (authorized.binding.metadata_ or {}).get("source") or "chat_surface"
    )
    runtime_request = ChatRuntimeRequest(
        project_id=authorized.surface.project_id,
        target_type=authorized.surface.target_type,
        target_id=authorized.surface.target_id,
        target_release_id=authorized.binding.target_release_id,
        session_id=authorized.binding.session_id,
        surface_id=authorized.surface.id,
        message_request_id=message_request.id,
        message=payload.message,
        metadata=dict(payload.metadata or {}),
        external_context=dict(payload.external_context or {}),
        session_source=session_source,
        created=created,
        existing_run_id=message_request.target_run_id,
    )

    try:
        prepared = await _runtime_gateway(request).prepare(
            runtime_request,
            request.is_disconnected,
        )
    except Exception:
        if created:
            await service.mark_message(
                message_request.id,
                status="failed",
                target_run_id=message_request.target_run_id,
                error_code="runtime_start_failed",
            )
        raise

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "X-Woobe-Message-Request-ID": str(message_request.id),
        **(prepared.headers or {}),
    }
    if prepared.run_id is not None:
        headers.setdefault("X-Woobe-Run-ID", str(prepared.run_id))

    # Current-state reconciliation supersedes transport cursor replay. The header is
    # accepted for compatibility but never drives execution or observer ownership.
    del last_event_id

    return StreamingResponse(
        _consume_runtime_stream(
            service,
            message_request_id=message_request.id,
            prepared=prepared,
        ),
        media_type="text/event-stream",
        headers=headers,
    )
