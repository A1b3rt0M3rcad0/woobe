from __future__ import annotations

from uuid import UUID

from shared.security.control_plane import MAX_AUTHORITY_REVISION

from fastapi import APIRouter, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from modules.core.entrypoint import build_control_key_service
from modules.identity.entrypoint import build_authority_service
from woobe_api.http.shared.preconditions import expected_revision
from shared.infra.errors import AuthenticationError
from shared.security.principal import SecurityPrincipal


router = APIRouter(prefix="/workspaces/{workspace_id}/control-keys", tags=["core"])


class ProjectGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    permissions: list[str] = Field(default_factory=list, max_length=64)
    conditions: dict[str, list[str]] | None = None
    category_id: UUID | None = None
    category_revision: int | None = Field(default=None, ge=1, le=MAX_AUTHORITY_REVISION)


class CreateControlKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(default_factory=list, max_length=32)
    project_grants: list[ProjectGrantRequest] = Field(
        default_factory=list, max_length=128
    )
    expires_at: AwareDatetime | None = None
    on_project_create_permissions: list[str] | None = Field(default=None, max_length=64)
    category_id: UUID | None = None
    category_revision: int | None = Field(default=None, ge=1, le=MAX_AUTHORITY_REVISION)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Control key name cannot be blank")
        return normalized


class UpdateControlKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] | None = Field(default=None, max_length=32)
    project_grants: list[ProjectGrantRequest] | None = Field(
        default=None, max_length=128
    )
    expires_at: AwareDatetime | None = None
    on_project_create_permissions: list[str] | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def non_nullable_updates(self):
        for field in (
            "name",
            "permissions",
            "project_grants",
            "on_project_create_permissions",
        ):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class RotateControlKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    expires_at: AwareDatetime | None = None


def _principal(request: Request) -> SecurityPrincipal:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise AuthenticationError("Authentication required")
    return principal


def _grants(items: list[ProjectGrantRequest] | None) -> list[dict] | None:
    if items is None:
        return None
    return [item.model_dump(exclude_none=True) for item in items]


def _service():
    return build_control_key_service(category_resolver=build_authority_service())


def _response(data: dict, code: int = 200):
    headers = {"ETag": data["etag"]} if data.get("etag") else {}
    if data.get("idempotency_replayed"):
        headers["Idempotency-Replayed"] = "true"
    return JSONResponse(
        jsonable_encoder({"success": True, "data": data}),
        status_code=code,
        headers=headers,
    )


@router.get("")
async def list_control_keys(workspace_id: UUID, request: Request):
    data = await _service().list_keys(
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
    data = await _service().create_key(
        actor=_principal(request),
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        permissions=list(payload.permissions),
        project_grants=_grants(payload.project_grants) or [],
        expires_at=payload.expires_at,
        on_project_create_permissions=payload.on_project_create_permissions,
        category_id=payload.category_id,
        category_revision=payload.category_revision,
        idempotency_key=request.headers.get("idempotency-key"),
    )
    return _response(data, 201)


@router.patch("/{control_key_id}")
async def update_control_key(
    workspace_id: UUID,
    control_key_id: UUID,
    payload: UpdateControlKeyRequest,
    request: Request,
):
    data = await _service().update_key(
        actor=_principal(request),
        workspace_id=workspace_id,
        control_key_id=control_key_id,
        name=payload.name,
        description=payload.description,
        description_supplied="description" in payload.model_fields_set,
        permissions=payload.permissions,
        project_grants=_grants(payload.project_grants),
        expires_at=payload.expires_at,
        expires_at_supplied="expires_at" in payload.model_fields_set,
        expected_revision=expected_revision(
            request, kind="control-key", resource_id=control_key_id
        ),
        on_project_create_permissions=payload.on_project_create_permissions,
    )
    return _response(data)


@router.post("/{control_key_id}/revoke")
async def revoke_control_key(
    workspace_id: UUID,
    control_key_id: UUID,
    request: Request,
):
    data = await _service().revoke_key(
        actor=_principal(request),
        workspace_id=workspace_id,
        control_key_id=control_key_id,
        expected_revision=expected_revision(
            request, kind="control-key", resource_id=control_key_id
        ),
    )
    return {"success": True, "message": "revoked", "data": data}


@router.post("/{control_key_id}/rotate", status_code=status.HTTP_201_CREATED)
async def rotate_control_key(
    workspace_id: UUID,
    control_key_id: UUID,
    payload: RotateControlKeyRequest,
    request: Request,
):
    data = await _service().rotate_key(
        actor=_principal(request),
        workspace_id=workspace_id,
        control_key_id=control_key_id,
        idempotency_key=request.headers.get("idempotency-key"),
        name=payload.name,
        expires_at=payload.expires_at,
        expires_at_supplied="expires_at" in payload.model_fields_set,
        expected_revision=expected_revision(
            request, kind="control-key", resource_id=control_key_id
        ),
    )
    return _response(data, 201)
