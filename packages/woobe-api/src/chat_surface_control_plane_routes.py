from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from modules.chat_surface.entrypoint import get_chat_surface_composer
from modules.core.entrypoint import (
    create_chat_surface_access_key_composer,
    list_chat_surface_access_keys_composer,
    revoke_chat_surface_access_key_composer,
    rotate_chat_surface_access_key_composer,
)
from shared.contracts.errors import AuthenticationError, ConflictError
from shared.presentation.http.adapter import request_adapter, response_adapter
from shared.presentation.http.request import Request as InternalRequest
from shared.security.principal import AuthenticatedPrincipal


router = APIRouter(tags=["chat-surfaces"])


class CreateSurfaceAccessKeyRequest(BaseModel):
    name: str = Field(default="Default ChatSurface key", min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)


def _principal(request: Request) -> AuthenticatedPrincipal:
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, AuthenticatedPrincipal):
        raise AuthenticationError("User authentication required")
    return principal


async def _surface_data(request: Request) -> dict:
    response = await request_adapter(request, get_chat_surface_composer())
    return dict(response.body["data"])


@router.post("/chat-surfaces/{surface_id}/access-keys", status_code=201)
async def create_access_key(
    surface_id: UUID,
    payload: CreateSurfaceAccessKeyRequest,
    request: Request,
):
    surface = await _surface_data(request)
    if surface["status"] == "archived":
        raise ConflictError("Archived ChatSurface cannot receive Access Keys")
    response = await create_chat_surface_access_key_composer()(
        InternalRequest(
            principal=_principal(request),
            path_params={"surface_id": str(surface_id)},
            body={
                "project_id": surface["project_id"],
                "name": payload.name,
                "description": payload.description,
            },
        )
    )
    return response_adapter(response)


@router.get("/chat-surfaces/{surface_id}/access-keys")
async def list_access_keys(surface_id: UUID, request: Request):
    del surface_id
    response = await request_adapter(
        request,
        list_chat_surface_access_keys_composer(),
    )
    return response_adapter(response)


@router.post(
    "/chat-surfaces/{surface_id}/access-keys/{api_key_id}/rotate",
    status_code=201,
)
async def rotate_access_key(
    surface_id: UUID,
    api_key_id: UUID,
    request: Request,
):
    del surface_id, api_key_id
    response = await request_adapter(
        request,
        rotate_chat_surface_access_key_composer(),
    )
    return response_adapter(response)


@router.post("/chat-surfaces/{surface_id}/access-keys/{api_key_id}/revoke")
async def revoke_access_key(
    surface_id: UUID,
    api_key_id: UUID,
    request: Request,
):
    del surface_id, api_key_id
    response = await request_adapter(
        request,
        revoke_chat_surface_access_key_composer(),
    )
    return response_adapter(response)


__all__ = ["router"]
