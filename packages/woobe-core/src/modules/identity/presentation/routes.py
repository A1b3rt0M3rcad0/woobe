from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest

from modules.identity.application.composers.get_workspace_composer import (
    get_workspace_composer,
)
from modules.identity.application.composers.get_user_composer import get_user_composer
from modules.identity.application.composers.update_workspace_composer import (
    update_workspace_composer,
)
from modules.identity.application.instance_service import InstanceService
from modules.identity.domain.enums import MemberRole
from modules.identity.presentation.auth_endpoints import (
    authentication_service,
    create_workspace_endpoint,
    csrf_endpoint,
    get_current_user_endpoint,
    list_workspaces_endpoint,
    login_endpoint,
    logout_endpoint,
    workspace_payload,
    refresh_endpoint,
    register_endpoint,
)
from shared.infra.errors import AuthenticationError, AuthorizationError, NotFoundError, ValidationError
from shared.presentation.http.adapter import request_adapter, response_adapter
from shared.security.workspace_access import WorkspaceAccessService


router = APIRouter(prefix="/identity", tags=["identity"])


def _principal_user_id(request: FastAPIRequest) -> UUID:
    principal = getattr(request.state, "principal", None)
    user_id = getattr(principal, "user_id", None)
    if user_id is None:
        raise AuthenticationError("Authentication required")
    return UUID(str(user_id))


def _workspace_access(request: FastAPIRequest) -> WorkspaceAccessService:
    return WorkspaceAccessService(request.app.state.session_factory)


def _instance_service(request: FastAPIRequest) -> InstanceService:
    return InstanceService(
        request.app.state.session_factory,
        request.app.state.access_token_codec,
        request.app.state.settings,
    )


def _uuid(value: str, field: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid {field}") from exc


@router.get("/workspaces")
async def list_workspaces(request: FastAPIRequest):
    return await list_workspaces_endpoint(request)


@router.get("/invites/pending")
async def list_pending_invites(request: FastAPIRequest):
    invites = await authentication_service(request).list_pending_invites(
        _principal_user_id(request)
    )
    return {"success": True, "message": "ok", "data": invites}


@router.post("/invites/{invite_id}/accept")
async def accept_invite(request: FastAPIRequest, invite_id: UUID):
    user_id = _principal_user_id(request)
    await _workspace_access(request).require_valid_invite_acceptance(
        user_id=user_id,
        invite_id=invite_id,
    )
    workspace = await authentication_service(request).accept_invite(
        user_id=user_id,
        invite_id=invite_id,
    )
    return {
        "success": True,
        "message": "accepted",
        "data": workspace_payload(workspace),
    }


@router.get("/users/me")
async def get_current_user(request: FastAPIRequest):
    return await get_current_user_endpoint(request)


@router.get("/auth/csrf")
async def csrf(request: FastAPIRequest):
    return await csrf_endpoint(request)


@router.post("/auth/login")
async def login(request: FastAPIRequest):
    return await login_endpoint(request)


@router.post("/auth/register")
async def register(request: FastAPIRequest):
    payload = dict(await request.json())
    email = payload.get("email")
    if not isinstance(email, str) or not email.strip():
        raise ValidationError("Registration email is required")
    await _instance_service(request).ensure_registration_allowed(email)
    return await register_endpoint(request)


@router.post("/auth/refresh")
async def refresh(request: FastAPIRequest):
    return await refresh_endpoint(request)


@router.post("/auth/logout")
async def logout(request: FastAPIRequest):
    return await logout_endpoint(request)


@router.post("/users")
async def create_user(request: FastAPIRequest):
    del request
    raise AuthorizationError("Users can only be created through registration or invitation")


@router.post("/workspaces")
async def create_workspace(request: FastAPIRequest):
    return await create_workspace_endpoint(request)


@router.post("/workspaces/{workspace_id}/members")
async def add_member(request: FastAPIRequest, workspace_id: str):
    del request, workspace_id
    raise AuthorizationError("Workspace membership is created by accepting an invitation")


@router.get("/workspaces/{workspace_id}")
async def get_workspace(request: FastAPIRequest, workspace_id: str):
    del workspace_id
    handler = get_workspace_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/workspaces/{workspace_id}")
async def update_workspace(request: FastAPIRequest, workspace_id: str):
    await _workspace_access(request).require_admin(
        _principal_user_id(request),
        _uuid(workspace_id, "workspace id"),
    )
    handler = update_workspace_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/workspaces/{workspace_id}/members")
async def list_members(request: FastAPIRequest, workspace_id: str):
    data = await _workspace_access(request).list_members(
        actor_user_id=_principal_user_id(request),
        workspace_id=_uuid(workspace_id, "workspace id"),
    )
    return {"success": True, "message": "ok", "data": data}


@router.delete("/workspaces/{workspace_id}/members/{target_user_id}")
async def remove_member(request: FastAPIRequest, workspace_id: str, target_user_id: UUID):
    data = await _workspace_access(request).remove_member(
        actor_user_id=_principal_user_id(request),
        workspace_id=_uuid(workspace_id, "workspace id"),
        target_user_id=target_user_id,
    )
    return {"success": True, "message": "removed", "data": data}


@router.post("/workspaces/{workspace_id}/invites", status_code=201)
async def create_invite(request: FastAPIRequest, workspace_id: str):
    principal_user_id = _principal_user_id(request)
    workspace_id = _uuid(workspace_id, "workspace id")
    payload = dict(await request.json())
    role_value = payload.get("role", "member")
    email = payload.get("email")
    project_values = payload.get("project_ids", [])
    if not isinstance(role_value, str):
        raise ValidationError("Invalid invite role")
    if not isinstance(email, str) or not email.strip():
        raise ValidationError("Invite email is required")
    if not isinstance(project_values, list):
        raise ValidationError("project_ids must be a list")
    try:
        role = MemberRole(role_value.strip().lower())
        project_ids = [UUID(str(value)) for value in project_values]
    except (ValueError, TypeError) as exc:
        raise ValidationError("Invalid invite role or Project id") from exc
    if role not in {MemberRole.member, MemberRole.admin}:
        raise ValidationError("Only member and admin invitation roles are supported in the MVP")

    await _workspace_access(request).require_role_assignment(
        actor_user_id=principal_user_id,
        workspace_id=workspace_id,
        target_role=role.value,
    )
    invite = await authentication_service(request).create_invite(
        actor_user_id=principal_user_id,
        workspace_id=workspace_id,
        email=email,
        role=role,
        project_ids=project_ids,
    )
    return {
        "success": True,
        "message": "created",
        "data": {
            "id": invite.id,
            "workspace_id": invite.workspace_id,
            "email": invite.email,
            "role": invite.role.value,
            "status": invite.status.value,
            "expires_at": invite.expires_at,
            "created_at": invite.created_at,
            "project_ids": project_ids,
            "project_count": len(project_ids),
        },
    }


@router.get("/workspaces/{workspace_id}/invites")
async def list_invites(request: FastAPIRequest, workspace_id: str):
    data = await _workspace_access(request).list_invites(
        actor_user_id=_principal_user_id(request),
        workspace_id=_uuid(workspace_id, "workspace id"),
    )
    return {"success": True, "message": "ok", "data": data}


@router.delete("/workspaces/{workspace_id}/invites/{invite_id}")
async def cancel_invite(request: FastAPIRequest, workspace_id: str, invite_id: UUID):
    data = await _workspace_access(request).cancel_invite(
        actor_user_id=_principal_user_id(request),
        workspace_id=_uuid(workspace_id, "workspace id"),
        invite_id=invite_id,
    )
    return {"success": True, "message": "cancelled", "data": data}


@router.get("/users/{user_id}")
async def get_user(request: FastAPIRequest, user_id: str):
    target_user_id = _uuid(user_id, "user id")
    if _principal_user_id(request) != target_user_id:
        raise NotFoundError("User not found")
    handler = get_user_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
