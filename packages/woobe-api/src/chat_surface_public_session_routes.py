from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from chat_surface_session_orchestration import (
    archive_bound_target_session,
    create_bound_target_session,
    get_binding,
)
from modules.chat_surface.entrypoint import (
    get_public_chat_surface_composer,
    issue_chat_surface_session_token_composer,
)
from modules.core.entrypoint import authenticate_chat_surface_access_key_composer
from shared.contracts.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
)
from shared.presentation.http.request import Request as InternalRequest
from shared.security.rate_limit import SlidingWindowRateLimiter


router = APIRouter(tags=["chat-surfaces"])


class CreateSurfaceSessionRequest(BaseModel):
    external_reference: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] | None = None


class IssueSessionTokenRequest(BaseModel):
    origin: str = Field(min_length=1, max_length=2048)


def _bearer(request: Request) -> str:
    scheme, _, credentials = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not credentials:
        raise AuthenticationError("Bearer authentication required")
    return credentials


async def _surface(public_id: str) -> dict:
    try:
        response = await get_public_chat_surface_composer()(
            InternalRequest(path_params={"public_id": public_id})
        )
    except NotFoundError as exc:
        raise AuthenticationError("Invalid ChatSurface Access Key") from exc
    return dict(response.body["data"])


async def _credential(surface: dict, request: Request) -> dict:
    response = await authenticate_chat_surface_access_key_composer()(
        InternalRequest(
            path_params={"surface_id": str(surface["id"])},
            body={"credentials": _bearer(request)},
        )
    )
    credential = dict(response.body["data"])
    if (
        UUID(str(credential["project_id"])) != UUID(str(surface["project_id"]))
        or UUID(str(credential["chat_surface_id"])) != UUID(str(surface["id"]))
    ):
        raise AuthenticationError("Invalid ChatSurface Access Key")
    return credential


def _require_scope(credential: dict, scope: str) -> None:
    if scope not in set(credential.get("scopes") or []):
        raise AuthorizationError("ChatSurface Access Key scope is not sufficient")


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
    surface = await _surface(public_id)
    credential = await _credential(surface, request)
    _require_scope(credential, "surface:sessions:create")
    credential_id = UUID(str(credential["id"]))
    await _consume_access_key_rate(
        request,
        credential_id=credential_id,
        namespace="chat_surface_session_create",
        limit=request.app.state.settings.chat_surface_session_create_rate_limit,
    )
    binding = await create_bound_target_session(
        surface=surface,
        surface_credential_id=credential_id,
        idempotency_key=idempotency_key,
        external_reference=payload.external_reference,
        metadata=payload.metadata,
    )
    return {"success": True, "data": binding}


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
    surface = await _surface(public_id)
    credential = await _credential(surface, request)
    _require_scope(credential, "surface:sessions:token:issue")
    credential_id = UUID(str(credential["id"]))
    await _consume_access_key_rate(
        request,
        credential_id=credential_id,
        namespace="chat_surface_token_issue",
        limit=request.app.state.settings.chat_surface_token_issue_rate_limit,
    )
    response = await issue_chat_surface_session_token_composer()(
        InternalRequest(
            path_params={
                "surface_id": str(surface["id"]),
                "session_id": str(session_id),
            },
            body={
                "surface_credential_id": str(credential_id),
                "origin": payload.origin,
            },
        )
    )
    return response.body


@router.post("/v1/chat-surfaces/{public_id}/sessions/{session_id}/archive")
async def archive_public_session(
    public_id: str,
    session_id: UUID,
    request: Request,
):
    surface = await _surface(public_id)
    credential = await _credential(surface, request)
    _require_scope(credential, "surface:sessions:archive")
    binding = await get_binding(
        surface_id=UUID(str(surface["id"])),
        session_id=session_id,
    )
    archived = await archive_bound_target_session(
        surface=surface,
        binding=binding,
    )
    return {"success": True, "data": archived}


__all__ = ["router"]
