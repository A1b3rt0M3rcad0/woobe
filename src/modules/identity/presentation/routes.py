from fastapi import APIRouter, Request as FastAPIRequest

from modules.identity.application.composers.add_member_composer import add_member_composer
from modules.identity.application.composers.create_invite_composer import (
    create_invite_composer,
)
from modules.identity.application.composers.create_organization_composer import (
    create_organization_composer,
)
from modules.identity.application.composers.create_user_composer import create_user_composer
from modules.identity.application.composers.get_organization_composer import (
    get_organization_composer,
)
from modules.identity.application.composers.get_user_composer import get_user_composer
from modules.identity.application.composers.list_invites_composer import (
    list_invites_composer,
)
from modules.identity.application.composers.list_members_composer import list_members_composer
from modules.identity.application.composers.update_organization_composer import (
    update_organization_composer,
)
from modules.identity.presentation.auth_endpoints import (
    get_current_user_endpoint,
    list_organizations_endpoint,
    login_endpoint,
    logout_endpoint,
    refresh_endpoint,
    register_endpoint,
)
from shared.infra.errors import AuthenticationError
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/identity", tags=["identity"])


@router.get("/organizations")
async def list_organizations(request: FastAPIRequest):
    return await list_organizations_endpoint(request)


@router.get("/users/me")
async def get_current_user(request: FastAPIRequest):
    return await get_current_user_endpoint(request)


@router.post("/auth/login")
async def login(request: FastAPIRequest):
    return await login_endpoint(request)


@router.post("/auth/register")
async def register(request: FastAPIRequest):
    return await register_endpoint(request)


@router.post("/auth/refresh")
async def refresh(request: FastAPIRequest):
    return await refresh_endpoint(request)


@router.post("/auth/logout")
async def logout(request: FastAPIRequest):
    return await logout_endpoint(request)


@router.post("/users")
async def create_user(request: FastAPIRequest):
    handler = create_user_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/organizations")
async def create_organization(request: FastAPIRequest):
    handler = create_organization_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/organizations/{org_id}/members")
async def add_member(request: FastAPIRequest):
    handler = add_member_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/organizations/{org_id}")
async def get_organization(request: FastAPIRequest):
    handler = get_organization_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/organizations/{org_id}")
async def update_organization(request: FastAPIRequest):
    handler = update_organization_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/organizations/{org_id}/members")
async def list_members(request: FastAPIRequest):
    handler = list_members_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/organizations/{org_id}/invites")
async def create_invite(request: FastAPIRequest):
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise AuthenticationError("Authentication required")
    payload = dict(await request.json())
    payload["invited_by_user_id"] = str(principal.user_id)
    request._body = __import__("json").dumps(payload).encode("utf-8")
    handler = create_invite_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/organizations/{org_id}/invites")
async def list_invites(request: FastAPIRequest):
    handler = list_invites_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/users/{user_id}")
async def get_user(request: FastAPIRequest):
    handler = get_user_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
