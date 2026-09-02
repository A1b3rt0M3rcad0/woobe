from fastapi import APIRouter, Request as FastAPIRequest

from modules.identity.application.instance_service import InstanceService
from modules.identity.composition.composers.authentication_composers import (
    accept_workspace_invite_composer,
    create_owned_workspace_composer,
    create_workspace_invite_authentication_composer,
    csrf_composer,
    get_authenticated_user_composer,
    list_authenticated_workspaces_composer,
    list_pending_workspace_invites_composer,
    login_authentication_composer,
    logout_authentication_composer,
    refresh_authentication_composer,
    register_authentication_composer,
)
from modules.identity.composition.composers.get_user_composer import get_user_composer
from modules.identity.composition.composers.get_workspace_composer import get_workspace_composer
from modules.identity.composition.composers.update_workspace_composer import update_workspace_composer
from modules.identity.composition.composers.workspace_access_composers import (
    cancel_workspace_invite_composer,
    list_workspace_invites_access_composer,
    list_workspace_members_access_composer,
    remove_workspace_member_composer,
)
from shared.contracts.errors import AuthorizationError, ValidationError
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/identity", tags=["identity"])


async def _handle(request: FastAPIRequest, handler):
    response = await request_adapter(request, handler)
    return response_adapter(response)


def _instance_service(request: FastAPIRequest) -> InstanceService:
    return InstanceService(
        request.app.state.session_factory,
        request.app.state.access_token_codec,
        request.app.state.settings,
    )


@router.get("/workspaces")
async def list_workspaces(request: FastAPIRequest):
    return await _handle(request, list_authenticated_workspaces_composer())


@router.get("/invites/pending")
async def list_pending_invites(request: FastAPIRequest):
    return await _handle(request, list_pending_workspace_invites_composer())


@router.post("/invites/{invite_id}/accept")
async def accept_invite(request: FastAPIRequest):
    return await _handle(request, accept_workspace_invite_composer())


@router.get("/users/me")
async def get_current_user(request: FastAPIRequest):
    return await _handle(request, get_authenticated_user_composer())


@router.get("/auth/csrf")
async def csrf(request: FastAPIRequest):
    return await _handle(request, csrf_composer())


@router.post("/auth/login")
async def login(request: FastAPIRequest):
    return await _handle(request, login_authentication_composer())


@router.post("/auth/register")
async def register(request: FastAPIRequest):
    payload = dict(await request.json())
    email = payload.get("email")
    if not isinstance(email, str) or not email.strip():
        raise ValidationError("Registration email is required")
    await _instance_service(request).ensure_registration_allowed(email)
    return await _handle(request, register_authentication_composer())


@router.post("/auth/refresh")
async def refresh(request: FastAPIRequest):
    return await _handle(request, refresh_authentication_composer())


@router.post("/auth/logout")
async def logout(request: FastAPIRequest):
    return await _handle(request, logout_authentication_composer())


@router.post("/users")
async def create_user(request: FastAPIRequest):
    del request
    raise AuthorizationError("Users can only be created through registration or invitation")


@router.post("/workspaces")
async def create_workspace(request: FastAPIRequest):
    return await _handle(request, create_owned_workspace_composer())


@router.post("/workspaces/{workspace_id}/members")
async def add_member(request: FastAPIRequest, workspace_id: str):
    del request, workspace_id
    raise AuthorizationError("Workspace membership is created by accepting an invitation")


@router.get("/workspaces/{workspace_id}")
async def get_workspace(request: FastAPIRequest):
    return await _handle(request, get_workspace_composer())


@router.patch("/workspaces/{workspace_id}")
async def update_workspace(request: FastAPIRequest):
    return await _handle(request, update_workspace_composer())


@router.get("/workspaces/{workspace_id}/members")
async def list_members(request: FastAPIRequest):
    return await _handle(request, list_workspace_members_access_composer())


@router.delete("/workspaces/{workspace_id}/members/{target_user_id}")
async def remove_member(request: FastAPIRequest):
    return await _handle(request, remove_workspace_member_composer())


@router.post("/workspaces/{workspace_id}/invites", status_code=201)
async def create_invite(request: FastAPIRequest):
    return await _handle(request, create_workspace_invite_authentication_composer())


@router.get("/workspaces/{workspace_id}/invites")
async def list_invites(request: FastAPIRequest):
    return await _handle(request, list_workspace_invites_access_composer())


@router.delete("/workspaces/{workspace_id}/invites/{invite_id}")
async def cancel_invite(request: FastAPIRequest):
    return await _handle(request, cancel_workspace_invite_composer())


@router.get("/users/{user_id}")
async def get_user(request: FastAPIRequest):
    return await _handle(request, get_user_composer())
