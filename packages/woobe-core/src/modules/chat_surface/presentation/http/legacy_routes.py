from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, Request

from modules.chat_surface.control_plane_service import (
    CONTROL_PLANE_TEST_SOURCE,
    ControlPlaneChatSurfaceService,
)
from modules.chat_surface.presentation.schemas import (
    CreateChatSurfaceRequest,
    CreateSurfaceAccessKeyRequest,
    CreateSurfaceSessionRequest,
    IssueSessionTokenRequest,
)
from modules.chat_surface.service import surface_payload
from shared.infra.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
)
from shared.security.principal import AuthenticatedPrincipal
from shared.security.rate_limit import SlidingWindowRateLimiter


router = APIRouter(tags=["chat-surfaces"])


def _service(request: Request) -> ControlPlaneChatSurfaceService:
    settings = request.app.state.settings
    if not settings.chat_surface_enabled:
        raise NotFoundError("ChatSurface is not enabled")
    local_environment = settings.environment.strip().lower() in {
        "development",
        "dev",
        "test",
        "local",
    }
    return ControlPlaneChatSurfaceService(
        request.app.state.session_factory,
        request.app.state.chat_session_token_codec,
        allow_insecure_origins=(
            settings.chat_surface_allow_insecure_origins or local_environment
        ),
        max_metadata_bytes=settings.runtime_max_metadata_bytes,
    )


def _authenticated_user(request: Request) -> UUID:
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, AuthenticatedPrincipal):
        raise AuthorizationError("User authentication required")
    return principal.user_id


def _bearer(request: Request) -> str:
    scheme, _, credentials = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not credentials:
        raise AuthenticationError("Bearer authentication required")
    return credentials


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
        actor_id=_authenticated_user(request),
        payload=payload,
    )
    return {"success": True, "data": surface_payload(surface)}


@router.post("/chat-surfaces/{surface_id}/release")
async def refresh_surface_release(surface_id: UUID, request: Request):
    _authenticated_user(request)
    surface = await _service(request).refresh_target_release(surface_id)
    return {"success": True, "data": surface_payload(surface)}


async def _set_surface_status(surface_id: UUID, request: Request, status: str):
    _authenticated_user(request)
    surface = await _service(request).set_status(surface_id, status)
    return {"success": True, "data": surface_payload(surface)}


@router.post("/chat-surfaces/{surface_id}/activate")
async def activate_surface(surface_id: UUID, request: Request):
    return await _set_surface_status(surface_id, request, "active")


@router.post("/chat-surfaces/{surface_id}/access-keys", status_code=201)
async def create_access_key(
    surface_id: UUID,
    payload: CreateSurfaceAccessKeyRequest,
    request: Request,
):
    api_key, secret, display_prefix = await _service(request).create_access_key(
        surface_id,
        actor_id=_authenticated_user(request),
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
    _authenticated_user(request)
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
    api_key, secret, display_prefix = await _service(request).rotate_access_key(
        surface_id,
        api_key_id,
        actor_id=_authenticated_user(request),
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
    _authenticated_user(request)
    api_key = await _service(request).revoke_access_key(surface_id, api_key_id)
    return {"success": True, "data": _key_payload(api_key)}


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
        actor_id=_authenticated_user(request),
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
    await SlidingWindowRateLimiter(
        namespace=namespace,
        limit=limit,
        window_seconds=60,
        message="ChatSurface Access Key rate limit exceeded",
        session_factory=request.app.state.session_factory,
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
