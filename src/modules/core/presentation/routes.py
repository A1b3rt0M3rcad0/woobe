from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest

from modules.core.application.composers.create_api_key_composer import create_api_key_composer
from modules.core.application.composers.create_project_composer import create_project_composer
from modules.core.application.composers.create_runtime_api_key_composer import create_runtime_api_key_composer
from modules.core.application.composers.get_project_composer import get_project_composer
from modules.core.application.composers.get_project_overview_composer import get_project_overview_composer
from modules.core.application.composers.list_api_keys_composer import list_api_keys_composer
from modules.core.application.composers.revoke_api_key_composer import revoke_api_key_composer
from modules.core.application.composers.rotate_api_key_composer import rotate_api_key_composer
from modules.core.application.composers.update_api_key_credential_composer import update_api_key_credential_composer
from modules.core.application.composers.update_project_composer import update_project_composer
from modules.core.application.workspace_project_access_service import ProjectAccessService
from modules.core.application.workspace_service import WorkspaceService
from shared.infra.errors import AuthenticationError, ValidationError
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/core", tags=["core"])


def _principal_user_id(request: FastAPIRequest) -> UUID:
    principal = getattr(request.state, "principal", None)
    user_id = getattr(principal, "user_id", None)
    if user_id is None:
        raise AuthenticationError("Authentication required")
    return UUID(str(user_id))


def _project_access_service(request: FastAPIRequest) -> ProjectAccessService:
    return ProjectAccessService(request.app.state.session_factory)


def _workspace_service(request: FastAPIRequest) -> WorkspaceService:
    return WorkspaceService(request.app.state.session_factory)


@router.get("/workspaces")
async def list_workspaces(request: FastAPIRequest):
    data = await _workspace_service(request).list_accessible(_principal_user_id(request))
    return {"success": True, "message": "ok", "data": data}


@router.post("/workspaces", status_code=201)
async def create_workspace(request: FastAPIRequest):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise ValidationError("Invalid Workspace payload")
    name = payload.get("name")
    slug = payload.get("slug")
    if not isinstance(name, str) or not isinstance(slug, str):
        raise ValidationError("Workspace name and slug are required")
    data = await _workspace_service(request).create(
        _principal_user_id(request), name, slug
    )
    return {"success": True, "message": "created", "data": data}


@router.get("/workspaces/{workspace_id}")
async def get_workspace(request: FastAPIRequest, workspace_id: UUID):
    data = await _workspace_service(request).get_accessible(
        _principal_user_id(request), workspace_id
    )
    return {"success": True, "message": "ok", "data": data}


@router.patch("/workspaces/{workspace_id}")
async def update_workspace(request: FastAPIRequest, workspace_id: UUID):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise ValidationError("Invalid Workspace payload")
    data = await _workspace_service(request).update(
        _principal_user_id(request),
        workspace_id,
        name=payload.get("name") if isinstance(payload.get("name"), str) else None,
        slug=payload.get("slug") if isinstance(payload.get("slug"), str) else None,
    )
    return {"success": True, "message": "updated", "data": data}


@router.get("/workspaces/{workspace_id}/members")
async def list_workspace_members(request: FastAPIRequest, workspace_id: UUID):
    data = await _workspace_service(request).list_members(
        _principal_user_id(request), workspace_id
    )
    return {"success": True, "message": "ok", "data": data}


@router.delete("/workspaces/{workspace_id}/members/{target_user_id}")
async def remove_workspace_member(
    request: FastAPIRequest, workspace_id: UUID, target_user_id: UUID
):
    await _workspace_service(request).remove_member(
        _principal_user_id(request), workspace_id, target_user_id
    )
    return {"success": True, "message": "removed", "data": None}


@router.get("/projects")
async def list_projects(request: FastAPIRequest):
    workspace_value = request.query_params.get("workspace_id")
    if not workspace_value:
        return {"success": True, "message": "ok", "data": []}
    try:
        workspace_id = UUID(str(workspace_value))
    except ValueError as exc:
        raise ValidationError("Invalid workspace_id") from exc
    projects = await _project_access_service(request).list_accessible_projects(
        user_id=_principal_user_id(request), workspace_id=workspace_id
    )
    return {"success": True, "message": "ok", "data": projects}


@router.post("/projects", status_code=201)
async def create_project(request: FastAPIRequest):
    payload = await request.json()
    workspace_value = payload.get("workspace_id") if isinstance(payload, dict) else None
    if workspace_value is None:
        raise ValidationError("workspace_id is required")
    try:
        workspace_id = UUID(str(workspace_value))
    except ValueError as exc:
        raise ValidationError("Invalid workspace_id") from exc
    actor = _principal_user_id(request)
    if not await _workspace_service(request).is_instance_admin(actor):
        from shared.infra.errors import AuthorizationError
        raise AuthorizationError("Only the Instance admin can create Projects")
    await _workspace_service(request).get_accessible(actor, workspace_id)
    handler = create_project_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/workspaces/{workspace_id}/project-access")
async def list_projects_for_access_management(
    request: FastAPIRequest, workspace_id: UUID
):
    if not await _workspace_service(request).is_instance_admin(_principal_user_id(request)):
        from shared.infra.errors import AuthorizationError
        raise AuthorizationError("Instance admin access is required")
    data = await _project_access_service(request).list_accessible_projects(
        user_id=_principal_user_id(request), workspace_id=workspace_id
    )
    return {"success": True, "message": "ok", "data": data}


@router.get("/projects/{access_project_id}/members")
async def list_project_members(request: FastAPIRequest, access_project_id: UUID):
    data = await _project_access_service(request).list_project_members(
        user_id=_principal_user_id(request), project_id=access_project_id
    )
    return {"success": True, "message": "ok", "data": data}


@router.post("/projects/{access_project_id}/members", status_code=201)
async def grant_project_access(request: FastAPIRequest, access_project_id: UUID):
    payload = await request.json()
    email = payload.get("email") if isinstance(payload, dict) else None
    if not isinstance(email, str) or not email.strip():
        raise ValidationError("email is required")
    data = await _project_access_service(request).grant_project_access(
        actor_user_id=_principal_user_id(request),
        project_id=access_project_id,
        email=email,
    )
    return {"success": True, "message": "created", "data": data}


@router.delete("/projects/{access_project_id}/members/{target_user_id}")
async def revoke_project_access(
    request: FastAPIRequest, access_project_id: UUID, target_user_id: UUID
):
    await _project_access_service(request).revoke_project_access(
        actor_user_id=_principal_user_id(request),
        project_id=access_project_id,
        target_user_id=target_user_id,
    )
    return {"success": True, "message": "deleted", "data": None}


@router.get("/projects/{project_id}/overview")
async def get_project_overview(request: FastAPIRequest):
    handler = get_project_overview_composer(request.app.state.session_factory)
    return response_adapter(await request_adapter(request, handler))


@router.get("/projects/{project_id}")
async def get_project(request: FastAPIRequest):
    handler = get_project_composer(request.app.state.session_factory)
    return response_adapter(await request_adapter(request, handler))


@router.patch("/projects/{project_id}")
async def update_project(request: FastAPIRequest):
    handler = update_project_composer(request.app.state.session_factory)
    return response_adapter(await request_adapter(request, handler))


@router.post("/projects/{project_id}/api-keys")
async def create_api_key(request: FastAPIRequest):
    return response_adapter(await request_adapter(request, create_api_key_composer(request.app.state.session_factory)))


@router.post("/projects/{project_id}/runtime-keys", status_code=201)
async def create_runtime_api_key(request: FastAPIRequest):
    return response_adapter(await request_adapter(request, create_runtime_api_key_composer(request.app.state.session_factory)))


@router.get("/projects/{project_id}/api-keys")
async def list_api_keys(request: FastAPIRequest):
    return response_adapter(await request_adapter(request, list_api_keys_composer(request.app.state.session_factory)))


@router.post("/projects/{project_id}/api-keys/{api_key_id}/revoke")
async def revoke_api_key(request: FastAPIRequest):
    return response_adapter(await request_adapter(request, revoke_api_key_composer(request.app.state.session_factory)))


@router.post("/projects/{project_id}/api-keys/{api_key_id}/rotate", status_code=201)
async def rotate_api_key(request: FastAPIRequest):
    return response_adapter(await request_adapter(request, rotate_api_key_composer(request.app.state.session_factory)))


@router.patch("/projects/{project_id}/api-keys/{api_key_id}")
async def update_api_key_credential(request: FastAPIRequest):
    return response_adapter(await request_adapter(request, update_api_key_credential_composer(request.app.state.session_factory)))
