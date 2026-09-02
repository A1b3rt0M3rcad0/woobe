from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

from modules.agent.entrypoint import build_agent_chat_surface_target_release_reader
from modules.chat_surface.entrypoint import (
    activate_chat_surface_composer,
    create_chat_surface_composer,
    get_chat_surface_composer,
    normalize_appearance_config,
    refresh_chat_surface_release_composer,
)
from modules.core.entrypoint import (
    create_chat_surface_access_key_composer,
    list_chat_surface_access_keys_composer,
    revoke_chat_surface_access_key_composer,
    rotate_chat_surface_access_key_composer,
)
from modules.network.entrypoint import build_network_chat_surface_target_release_reader
from shared.contracts.errors import AuthenticationError, ConflictError
from shared.presentation.http.adapter import request_adapter, response_adapter
from shared.presentation.http.request import Request as InternalRequest
from shared.security.principal import AuthenticatedPrincipal


router = APIRouter(tags=["chat-surfaces"])


class CreateChatSurfaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    target_type: str
    target_id: UUID
    allowed_origins: list[str] = Field(default_factory=list, max_length=32)
    appearance_config: dict[str, Any] = Field(default_factory=dict)
    requests_per_minute: int = Field(default=30, ge=1, le=10_000)
    max_concurrent_runs: int = Field(default=10, ge=1, le=100)
    session_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("ChatSurface name cannot be blank")
        return normalized

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"agent", "network"}:
            raise ValueError("target_type must be agent or network")
        return normalized

    @field_validator("appearance_config")
    @classmethod
    def validate_appearance_config(cls, value: dict[str, Any]) -> dict[str, Any]:
        return normalize_appearance_config(value)


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


def _target_release_reader(target_type: str):
    if target_type == "agent":
        return build_agent_chat_surface_target_release_reader()
    return build_network_chat_surface_target_release_reader()


@router.post("/chat-surfaces/projects/{project_id}", status_code=201)
async def create_surface(
    project_id: UUID,
    payload: CreateChatSurfaceRequest,
    request: Request,
):
    release = await _target_release_reader(payload.target_type).current(
        project_id=project_id,
        target_id=payload.target_id,
    )
    response = await create_chat_surface_composer()(
        InternalRequest(
            principal=_principal(request),
            path_params={"project_id": str(project_id)},
            body={
                **payload.model_dump(),
                "target_release_id": str(release.id),
            },
        )
    )
    return response_adapter(response)


@router.post("/chat-surfaces/{surface_id}/release")
async def refresh_surface_release(surface_id: UUID, request: Request):
    surface = await _surface_data(request)
    release = await _target_release_reader(surface["target_type"]).current(
        project_id=UUID(str(surface["project_id"])),
        target_id=UUID(str(surface["target_id"])),
    )
    response = await refresh_chat_surface_release_composer()(
        InternalRequest(
            principal=_principal(request),
            path_params={"surface_id": str(surface_id)},
            body={"target_release_id": str(release.id)},
        )
    )
    return response_adapter(response)


@router.post("/chat-surfaces/{surface_id}/activate")
async def activate_surface(surface_id: UUID, request: Request):
    surface = await _surface_data(request)
    release_id = UUID(str(surface["target_release_id"]))
    await _target_release_reader(surface["target_type"]).validate(
        project_id=UUID(str(surface["project_id"])),
        target_id=UUID(str(surface["target_id"])),
        release_id=release_id,
    )
    response = await activate_chat_surface_composer()(
        InternalRequest(
            principal=_principal(request),
            path_params={"surface_id": str(surface_id)},
            body={"expected_target_release_id": str(release_id)},
        )
    )
    return response_adapter(response)


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
