from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from modules.identity.entrypoint import build_authority_service
from shared.contracts.errors import AuthenticationError
from woobe_api.http.shared.preconditions import expected_revision

router = APIRouter(prefix="/identity", tags=["authority"])


class CategoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=500)
    scope: Literal["workspace", "project"] = "project"
    permissions: list[str] = Field(max_length=128)
    conditions: dict[str, Any] | None = None
    catalog_revision: str | None = Field(default=None, max_length=64)


class CategoryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(default=None, max_length=128)
    conditions: dict[str, Any] = Field(default=None)
    catalog_revision: str = Field(default=None, max_length=64)


class CategoryCloneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=500)
    revision: int | None = Field(default=None, ge=1)


def _actor(request: Request):
    actor = getattr(request.state, "principal", None)
    if actor is None:
        raise AuthenticationError("Authentication required")
    return actor


def _category_response(data: dict[str, Any], status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        jsonable_encoder({"success": True, "data": data}),
        status_code=status_code,
        headers={"ETag": f'"category:{data["id"]}:{data["revision"]}"'},
    )


@router.get("/workspaces/{workspace_id}/authority-categories")
async def list_authority_categories(
    workspace_id: UUID,
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
    cursor: UUID | None = None,
):
    return {
        "success": True,
        "data": await build_authority_service().list_categories(
            actor=_actor(request), workspace_id=workspace_id, limit=limit, cursor=cursor
        ),
    }


@router.post("/workspaces/{workspace_id}/authority-categories", status_code=201)
async def create_authority_category(
    workspace_id: UUID, payload: CategoryCreateRequest, request: Request
):
    data = await build_authority_service().create_category(
        actor=_actor(request), workspace_id=workspace_id, data=payload.model_dump()
    )
    return _category_response(data, 201)


@router.get("/workspaces/{workspace_id}/authority-categories/{category_id}")
async def get_authority_category(
    workspace_id: UUID,
    category_id: UUID,
    request: Request,
    revision: int | None = Query(default=None, ge=1),
):
    return _category_response(
        await build_authority_service().get_category(
            actor=_actor(request),
            workspace_id=workspace_id,
            category_id=category_id,
            revision=revision,
        )
    )


@router.patch("/workspaces/{workspace_id}/authority-categories/{category_id}")
async def update_authority_category(
    workspace_id: UUID,
    category_id: UUID,
    payload: CategoryUpdateRequest,
    request: Request,
):
    data = await build_authority_service().update_category(
        actor=_actor(request),
        workspace_id=workspace_id,
        category_id=category_id,
        expected_revision=expected_revision(
            request, kind="category", resource_id=category_id
        ),
        changes=payload.model_dump(exclude_unset=True),
    )
    return _category_response(data)


@router.post(
    "/workspaces/{workspace_id}/authority-categories/{category_id}/clone",
    status_code=201,
)
async def clone_authority_category(
    workspace_id: UUID,
    category_id: UUID,
    payload: CategoryCloneRequest,
    request: Request,
):
    service = build_authority_service()
    original = await service.get_category(
        actor=_actor(request),
        workspace_id=workspace_id,
        category_id=category_id,
        revision=payload.revision,
    )
    data = {
        "name": payload.name,
        "description": payload.description
        if "description" in payload.model_fields_set
        else original["description"],
        "scope": original["scope"],
        "permissions": original["permissions"],
        "conditions": original["conditions"],
        "catalog_revision": original["catalog_revision"],
    }
    return _category_response(
        await service.create_category(
            actor=_actor(request), workspace_id=workspace_id, data=data
        ),
        201,
    )


@router.get("/workspaces/{workspace_id}/authority-categories/{category_id}/versions")
async def authority_category_history(
    workspace_id: UUID,
    category_id: UUID,
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
    before_revision: int | None = Query(default=None, ge=1),
):
    return {
        "success": True,
        "data": await build_authority_service().category_history(
            actor=_actor(request),
            workspace_id=workspace_id,
            category_id=category_id,
            limit=limit,
            before_revision=before_revision,
        ),
    }


@router.post("/workspaces/{workspace_id}/authority-categories/{category_id}/archive")
async def archive_authority_category(
    workspace_id: UUID, category_id: UUID, request: Request
):
    return _category_response(
        await build_authority_service().update_category(
            actor=_actor(request),
            workspace_id=workspace_id,
            category_id=category_id,
            expected_revision=expected_revision(
                request, kind="category", resource_id=category_id
            ),
            changes={},
            archive=True,
        )
    )


@router.delete("/workspaces/{workspace_id}/authority-categories/{category_id}")
async def delete_authority_category(
    workspace_id: UUID, category_id: UUID, request: Request
):
    await build_authority_service().delete_category(
        actor=_actor(request),
        workspace_id=workspace_id,
        category_id=category_id,
        expected_revision=expected_revision(
            request, kind="category", resource_id=category_id
        ),
    )
    return {"success": True, "message": "deleted"}


class AccessCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str = Field(min_length=1, max_length=2048, pattern=r"^/[^?#]*$")
    query: dict[str, Any] = Field(default_factory=dict)
    body: dict[str, Any] = Field(default_factory=dict)


class AssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category_id: UUID
    category_revision: int | None = Field(default=None, ge=1)
    project_id: UUID | None = None


@router.get("/permissions")
async def permission_catalog(request: Request):
    from woobe_api.security.operation_catalog import operation_catalog
    from shared.security.control_plane import (
        PROJECT_CONTROL_PERMISSIONS,
        SELF_CONTROL_PERMISSIONS,
        WORKSPACE_CONTROL_PERMISSIONS,
    )

    _actor(request)
    catalog = operation_catalog(request.app.routes)
    catalog["permissions"] = {
        "self": sorted(SELF_CONTROL_PERMISSIONS),
        "workspace": sorted(WORKSPACE_CONTROL_PERMISSIONS),
        "project": sorted(PROJECT_CONTROL_PERMISSIONS),
    }
    return {"success": True, "data": catalog}


@router.get("/access/me")
async def effective_authority(
    request: Request, workspace_id: UUID | None = None, project_id: UUID | None = None
):
    from shared.contracts.errors import ValidationError
    from shared.security.principal import ControlPlanePrincipal

    actor = _actor(request)
    if workspace_id is None and isinstance(actor, ControlPlanePrincipal):
        workspace_id = actor.workspace_id
    if workspace_id is None:
        raise ValidationError("workspace_id is required for human access discovery")
    return {
        "success": True,
        "data": await build_authority_service().effective_access(
            actor=actor, workspace_id=workspace_id, project_id=project_id
        ),
    }


@router.post("/access/check")
async def check_authority(payload: AccessCheckRequest, request: Request):
    from woobe_api.security.operation_catalog import resolve_operation

    permission, params = resolve_operation(payload.method, payload.path, payload.body)
    decision = await build_authority_service().check_access(
        actor=_actor(request),
        permission=permission,
        path_params=params,
        query_params=payload.query,
        body=payload.body,
        mutation=payload.method != "GET",
    )
    return {"success": True, "data": decision}


@router.put("/workspaces/{workspace_id}/authority-assignments/{subject_user_id}")
async def assign_authority(
    workspace_id: UUID,
    subject_user_id: UUID,
    payload: AssignmentRequest,
    request: Request,
):
    from uuid import NAMESPACE_URL, uuid5

    assignment_id = uuid5(
        NAMESPACE_URL,
        f"woobe:{workspace_id}:assignment:{subject_user_id}:{payload.project_id or workspace_id}",
    )
    revision = (
        0
        if request.headers.get("if-none-match") == "*"
        else expected_revision(request, kind="assignment", resource_id=assignment_id)
    )
    data = await build_authority_service().assign_category(
        actor=_actor(request),
        workspace_id=workspace_id,
        subject_user_id=subject_user_id,
        category_id=payload.category_id,
        category_revision=payload.category_revision,
        project_id=payload.project_id,
        expected_revision=revision,
    )
    return JSONResponse(
        jsonable_encoder({"success": True, "data": data}),
        headers={"ETag": f'"assignment:{assignment_id}:{data["revision"]}"'},
    )


@router.get("/workspaces/{workspace_id}/authority-audit")
async def authority_audit(
    workspace_id: UUID,
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
    cursor: UUID | None = None,
):
    return {
        "success": True,
        "data": await build_authority_service().list_audit(
            actor=_actor(request), workspace_id=workspace_id, limit=limit, cursor=cursor
        ),
    }
