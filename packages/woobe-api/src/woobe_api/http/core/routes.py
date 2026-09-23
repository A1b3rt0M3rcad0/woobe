from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.entrypoint import project_environment_tool_usage_composer

from modules.core.entrypoint import (
    create_api_key_composer,
)
from modules.core.entrypoint import (
    create_project_composer,
)
from modules.core.entrypoint import (
    create_runtime_api_key_composer,
)
from modules.core.entrypoint import get_project_composer
from modules.core.entrypoint import (
    get_project_overview_composer,
    get_project_runs_composer,
)
from modules.core.entrypoint import (
    list_api_keys_composer,
)
from modules.core.entrypoint import (
    revoke_api_key_composer,
)
from modules.core.entrypoint import (
    rotate_api_key_composer,
)
from modules.core.entrypoint import (
    update_project_composer,
)
from modules.core.entrypoint import (
    update_api_key_credential_composer,
)
from modules.core.entrypoint import (
    ProjectAccessService,
    build_control_key_service,
    build_project_access_service,
)
from shared.infra.errors import AuthenticationError, ConflictError, ValidationError
from shared.project_environment import build_project_environment_service
from shared.security.principal import ControlPlanePrincipal
from woobe_api.http.shared.adapters import request_adapter, response_adapter
from woobe_api.http.core.control_key_routes import router as control_key_router

router = APIRouter(prefix="/core", tags=["core"])
router.include_router(control_key_router)


def _principal_user_id(request: FastAPIRequest) -> UUID:
    principal = getattr(request.state, "principal", None)
    user_id = getattr(principal, "user_id", None)
    if user_id is None:
        raise AuthenticationError("Authentication required")
    return UUID(str(user_id))


def _project_access_service(request: FastAPIRequest) -> ProjectAccessService:
    del request
    return build_project_access_service()


def _project_access_actor(
    request: FastAPIRequest,
) -> tuple[UUID | None, bool]:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, ControlPlanePrincipal):
        return None, True
    return _principal_user_id(request), False


async def _require_project_access(
    request: FastAPIRequest,
    project_id: UUID,
) -> None:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, ControlPlanePrincipal):
        return
    await _project_access_service(request).require_project_access(
        user_id=_principal_user_id(request),
        project_id=project_id,
    )


async def _project_environment_tool_usage(
    request: FastAPIRequest,
) -> dict[str, list[dict[str, str]]]:
    response = await request_adapter(
        request,
        project_environment_tool_usage_composer(),
    )
    data = response.body.get("data") if isinstance(response.body, dict) else None
    return data if isinstance(data, dict) else {}


@router.get("/projects")
async def list_projects(request: FastAPIRequest):
    workspace_id = request.query_params.get("workspace_id")
    if not workspace_id:
        return {"success": True, "message": "ok", "data": []}
    try:
        workspace_uuid = UUID(str(workspace_id))
    except ValueError as exc:
        raise ValidationError("Invalid workspace_id") from exc
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, ControlPlanePrincipal):
        if principal.workspace_id != workspace_uuid:
            return {"success": True, "message": "ok", "data": []}
        projects = await build_control_key_service().list_accessible_projects(
            principal=principal,
        )
    else:
        projects = await _project_access_service(request).list_accessible_projects(
            user_id=_principal_user_id(request),
            workspace_id=workspace_uuid,
        )
    return {"success": True, "message": "ok", "data": projects}


@router.post("/projects")
async def create_project(request: FastAPIRequest):
    payload = await request.json()
    workspace_id = payload.get("workspace_id") if isinstance(payload, dict) else None
    if workspace_id is None:
        raise ValidationError("workspace_id is required")
    try:
        workspace_uuid = UUID(str(workspace_id))
    except ValueError as exc:
        raise ValidationError("Invalid workspace_id") from exc

    principal = getattr(request.state, "principal", None)
    control_principal = (
        principal if isinstance(principal, ControlPlanePrincipal) else None
    )
    access = _project_access_service(request)
    user_id: UUID | None = None
    if control_principal is None:
        user_id = _principal_user_id(request)
        await access.require_workspace_admin(user_id, workspace_uuid)

    handler = create_project_composer()
    response = await request_adapter(request, handler)
    if response.status_code == 201 and isinstance(response.body, dict):
        data = response.body.get("data")
        if isinstance(data, dict) and data.get("id"):
            project_id = UUID(str(data["id"]))
            if control_principal is not None:
                await build_control_key_service().grant_created_project(
                    principal=control_principal,
                    project_id=project_id,
                )
            elif user_id is not None:
                await access.ensure_creator_access(
                    actor_user_id=user_id,
                    project_id=project_id,
                )
    return response_adapter(response)


@router.get("/workspaces/{workspace_id}/project-access")
async def list_projects_for_access_management(
    request: FastAPIRequest,
    workspace_id: UUID,
):
    projects = await _project_access_service(request).list_projects_for_access_management(
        user_id=_principal_user_id(request),
        workspace_id=workspace_id,
    )
    return {"success": True, "message": "ok", "data": projects}


@router.get("/projects/{access_project_id}/members")
async def list_project_members(request: FastAPIRequest, access_project_id: UUID):
    actor_user_id, control_plane_authorized = _project_access_actor(request)
    data = await _project_access_service(request).list_project_members(
        user_id=actor_user_id,
        project_id=access_project_id,
        control_plane_authorized=control_plane_authorized,
    )
    return {"success": True, "message": "ok", "data": data}


@router.post("/projects/{access_project_id}/access", status_code=201)
async def grant_project_subject_access(request: FastAPIRequest, access_project_id: UUID):
    payload = await request.json()
    subject_type = payload.get("subject_type") if isinstance(payload, dict) else None
    subject_id = payload.get("subject_id") if isinstance(payload, dict) else None
    if subject_type not in {"member", "invite"}:
        raise ValidationError("subject_type must be member or invite")
    try:
        subject_uuid = UUID(str(subject_id))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Invalid subject_id") from exc
    actor_user_id, control_plane_authorized = _project_access_actor(request)
    data = await _project_access_service(request).grant_project_subject_access(
        actor_user_id=actor_user_id,
        project_id=access_project_id,
        subject_type=subject_type,
        subject_id=subject_uuid,
        control_plane_authorized=control_plane_authorized,
    )
    return {"success": True, "message": "created", "data": data}


@router.delete("/projects/{access_project_id}/access/{subject_type}/{subject_id}")
async def revoke_project_subject_access(
    request: FastAPIRequest,
    access_project_id: UUID,
    subject_type: str,
    subject_id: UUID,
):
    if subject_type not in {"member", "invite"}:
        raise ValidationError("subject_type must be member or invite")
    actor_user_id, control_plane_authorized = _project_access_actor(request)
    await _project_access_service(request).revoke_project_subject_access(
        actor_user_id=actor_user_id,
        project_id=access_project_id,
        subject_type=subject_type,
        subject_id=subject_id,
        control_plane_authorized=control_plane_authorized,
    )
    return {"success": True, "message": "deleted", "data": None}


@router.post("/projects/{access_project_id}/members", status_code=201)
async def grant_project_access(request: FastAPIRequest, access_project_id: UUID):
    payload = await request.json()
    email = payload.get("email") if isinstance(payload, dict) else None
    if not isinstance(email, str) or not email.strip():
        raise ValidationError("email is required")
    actor_user_id, control_plane_authorized = _project_access_actor(request)
    member = await _project_access_service(request).grant_project_access(
        actor_user_id=actor_user_id,
        project_id=access_project_id,
        email=email,
        control_plane_authorized=control_plane_authorized,
    )
    return {"success": True, "message": "created", "data": member}


@router.delete("/projects/{access_project_id}/members/{target_user_id}")
async def revoke_project_access(
    request: FastAPIRequest,
    access_project_id: UUID,
    target_user_id: UUID,
):
    actor_user_id, control_plane_authorized = _project_access_actor(request)
    await _project_access_service(request).revoke_project_access(
        actor_user_id=actor_user_id,
        project_id=access_project_id,
        target_user_id=target_user_id,
        control_plane_authorized=control_plane_authorized,
    )
    return {"success": True, "message": "deleted", "data": None}


@router.get("/projects/{project_id}/overview")
async def get_project_overview(request: FastAPIRequest):
    handler = get_project_overview_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/projects/{project_id}/runs")
async def get_project_runs(request: FastAPIRequest):
    handler = get_project_runs_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/projects/{project_id}")
async def get_project(request: FastAPIRequest):
    handler = get_project_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/projects/{project_id}")
async def update_project(request: FastAPIRequest):
    handler = update_project_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/projects/{project_id}/environment-keys")
async def list_project_environment_keys(
    request: FastAPIRequest,
    project_id: UUID,
):
    await _require_project_access(request, project_id)
    data = await build_project_environment_service().list_keys(project_id=project_id)
    usage = await _project_environment_tool_usage(request)
    for item in data:
        item["used_by_tools"] = usage.get(str(item["key"]), [])
    return {"success": True, "message": "ok", "data": data}


@router.put("/projects/{project_id}/environment-keys/{key}")
async def upsert_project_environment_key(
    request: FastAPIRequest,
    project_id: UUID,
    key: str,
):
    await _require_project_access(request, project_id)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise ValidationError("Project Environment payload must be an object")
    values = payload.get("values") or {}
    if not isinstance(values, dict):
        raise ValidationError("Project Environment values must be an object")
    clear_environments = payload.get("clear_environments") or []
    if not isinstance(clear_environments, list):
        raise ValidationError("clear_environments must be an array")
    data = await build_project_environment_service().upsert_key(
        project_id=project_id,
        key=key,
        kind=str(payload.get("kind") or "value"),
        values=values,
        clear_environments=[str(item) for item in clear_environments],
    )
    return {"success": True, "message": "ok", "data": data}


@router.delete("/projects/{project_id}/environment-keys/{key}")
async def delete_project_environment_key(
    request: FastAPIRequest,
    project_id: UUID,
    key: str,
):
    await _require_project_access(request, project_id)
    references = (await _project_environment_tool_usage(request)).get(key, [])
    if references:
        names = ", ".join(item["name"] for item in references)
        raise ConflictError(
            f"Project Environment key '{key}' is used by Tool(s): {names}. "
            "Edit or delete those Tools before removing this key."
        )

    await build_project_environment_service().delete_key(
        project_id=project_id,
        key=key,
    )
    return {"success": True, "message": "deleted", "data": None}


@router.post("/projects/{project_id}/api-keys")
async def create_api_key(request: FastAPIRequest):
    handler = create_api_key_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/projects/{project_id}/runtime-keys", status_code=201)
async def create_runtime_api_key(request: FastAPIRequest):
    handler = create_runtime_api_key_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/projects/{project_id}/api-keys")
async def list_api_keys(request: FastAPIRequest):
    handler = list_api_keys_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/projects/{project_id}/api-keys/{api_key_id}/revoke")
async def revoke_api_key(request: FastAPIRequest):
    handler = revoke_api_key_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/projects/{project_id}/api-keys/{api_key_id}/rotate", status_code=201)
async def rotate_api_key(request: FastAPIRequest):
    handler = rotate_api_key_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/projects/{project_id}/api-keys/{api_key_id}")
async def update_api_key_credential(request: FastAPIRequest):
    handler = update_api_key_credential_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)
