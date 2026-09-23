from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field, field_validator

from modules.core.entrypoint import build_control_key_service
from shared.infra.errors import AuthenticationError
from shared.security.principal import SecurityPrincipal


router = APIRouter(prefix="/workspaces/{workspace_id}/control-keys", tags=["core"])


class ProjectGrantRequest(BaseModel):
    project_id: UUID
    permissions: list[str] = Field(min_length=1, max_length=64)


class CreateControlKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(default_factory=list, max_length=32)
    project_grants: list[ProjectGrantRequest] = Field(default_factory=list, max_length=128)
    expires_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Control key name cannot be blank")
        return normalized


class UpdateControlKeyRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] | None = Field(default=None, max_length=32)
    project_grants: list[ProjectGrantRequest] | None = Field(default=None, max_length=128)
    expires_at: datetime | None = None


class RotateControlKeyRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    expires_at: datetime | None = None


def _principal(request: Request) -> SecurityPrincipal:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise AuthenticationError("Authentication required")
    return principal


def _grants(items: list[ProjectGrantRequest] | None) -> list[dict] | None:
    if items is None:
        return None
    return [
        {
            "project_id": item.project_id,
            "permissions": list(item.permissions),
        }
        for item in items
    ]


@router.get("")
async def list_control_keys(workspace_id: UUID, request: Request):
    data = await build_control_key_service().list_keys(
        actor=_principal(request),
        workspace_id=workspace_id,
    )
    return {"success": True, "message": "ok", "data": data}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_control_key(
    workspace_id: UUID,
    payload: CreateControlKeyRequest,
    request: Request,
):
    data = await build_control_key_service().create_key(
        actor=_principal(request),
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        permissions=list(payload.permissions),
        project_grants=_grants(payload.project_grants) or [],
        expires_at=payload.expires_at,
    )
    return {"success": True, "message": "created", "data": data}


@router.patch("/{control_key_id}")
async def update_control_key(
    workspace_id: UUID,
    control_key_id: UUID,
    payload: UpdateControlKeyRequest,
    request: Request,
):
    data = await build_control_key_service().update_key(
        actor=_principal(request),
        workspace_id=workspace_id,
        control_key_id=control_key_id,
        name=payload.name,
        description=payload.description,
        permissions=payload.permissions,
        project_grants=_grants(payload.project_grants),
        expires_at=payload.expires_at,
        expires_at_supplied="expires_at" in payload.model_fields_set,
    )
    return {"success": True, "message": "ok", "data": data}


@router.post("/{control_key_id}/revoke")
async def revoke_control_key(
    workspace_id: UUID,
    control_key_id: UUID,
    request: Request,
):
    data = await build_control_key_service().revoke_key(
        actor=_principal(request),
        workspace_id=workspace_id,
        control_key_id=control_key_id,
    )
    return {"success": True, "message": "revoked", "data": data}


@router.post("/{control_key_id}/rotate", status_code=status.HTTP_201_CREATED)
async def rotate_control_key(
    workspace_id: UUID,
    control_key_id: UUID,
    payload: RotateControlKeyRequest,
    request: Request,
):
    data = await build_control_key_service().rotate_key(
        actor=_principal(request),
        workspace_id=workspace_id,
        control_key_id=control_key_id,
        name=payload.name,
        expires_at=payload.expires_at,
        expires_at_supplied="expires_at" in payload.model_fields_set,
    )
    return {"success": True, "message": "rotated", "data": data}
