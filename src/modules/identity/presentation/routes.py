from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest

from modules.identity.application.instance_service import InstanceService
from modules.identity.presentation.auth_endpoints import (
    authentication_service,
    csrf_endpoint,
    get_current_user_endpoint,
    login_endpoint,
    logout_endpoint,
    refresh_endpoint,
    register_endpoint,
)
from shared.infra.errors import AuthenticationError, AuthorizationError, ValidationError

router = APIRouter(prefix="/identity", tags=["identity"])


def _principal_user_id(request: FastAPIRequest) -> UUID:
    principal = getattr(request.state, "principal", None)
    user_id = getattr(principal, "user_id", None)
    if user_id is None:
        raise AuthenticationError("Authentication required")
    return UUID(str(user_id))


def _instance_service(request: FastAPIRequest) -> InstanceService:
    return InstanceService(
        request.app.state.session_factory,
        request.app.state.access_token_codec,
        request.app.state.settings,
    )


@router.get("/invites/pending")
async def list_pending_invites(request: FastAPIRequest):
    data = await authentication_service(request).list_pending_invites(
        _principal_user_id(request)
    )
    return {"success": True, "message": "ok", "data": data}


@router.post("/invites/{invite_id}/accept")
async def accept_invite(request: FastAPIRequest, invite_id: UUID):
    data = await authentication_service(request).accept_invite(
        user_id=_principal_user_id(request), invite_id=invite_id
    )
    return {"success": True, "message": "accepted", "data": data}


@router.post("/invites", status_code=201)
async def create_invite(request: FastAPIRequest):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise ValidationError("Invalid invite payload")
    email = payload.get("email")
    workspace_value = payload.get("workspace_id")
    project_values = payload.get("project_ids", [])
    if not isinstance(email, str) or not email.strip():
        raise ValidationError("Invite email is required")
    if not isinstance(project_values, list):
        raise ValidationError("project_ids must be a list")
    try:
        workspace_id = UUID(str(workspace_value))
        project_ids = [UUID(str(value)) for value in project_values]
    except (ValueError, TypeError) as exc:
        raise ValidationError("Invalid Workspace or Project id") from exc
    invite = await authentication_service(request).create_invite(
        actor_user_id=_principal_user_id(request),
        workspace_id=workspace_id,
        email=email,
        project_ids=project_ids,
    )
    return {
        "success": True,
        "message": "created",
        "data": {
            "id": invite.id,
            "workspace_id": invite.workspace_id,
            "email": invite.email,
            "status": invite.status.value,
            "expires_at": invite.expires_at,
            "created_at": invite.created_at,
            "project_ids": project_ids,
            "project_count": len(project_ids),
        },
    }


@router.get("/invites")
async def list_invites(request: FastAPIRequest):
    workspace_value = request.query_params.get("workspace_id")
    if not workspace_value:
        raise ValidationError("workspace_id is required")
    try:
        workspace_id = UUID(workspace_value)
    except ValueError as exc:
        raise ValidationError("Invalid workspace_id") from exc
    data = await authentication_service(request).list_invites(
        actor_user_id=_principal_user_id(request), workspace_id=workspace_id
    )
    return {"success": True, "message": "ok", "data": data}


@router.delete("/invites/{invite_id}")
async def cancel_invite(request: FastAPIRequest, invite_id: UUID):
    await authentication_service(request).cancel_invite(
        actor_user_id=_principal_user_id(request), invite_id=invite_id
    )
    return {"success": True, "message": "cancelled", "data": None}


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
