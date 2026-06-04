from fastapi import APIRouter, Request as FastAPIRequest

from modules.identity.application.composers.list_organizations_composer import list_organizations_composer
from modules.identity.application.composers.login_composer import login_composer
from modules.identity.application.composers.register_composer import register_composer
from modules.identity.application.composers.create_user_composer import create_user_composer
from modules.identity.application.composers.create_organization_composer import create_organization_composer
from modules.identity.application.composers.add_member_composer import add_member_composer
from modules.identity.application.composers.get_organization_composer import get_organization_composer
from modules.identity.application.composers.update_organization_composer import update_organization_composer
from modules.identity.application.composers.list_members_composer import list_members_composer
from modules.identity.application.composers.create_invite_composer import create_invite_composer
from modules.identity.application.composers.list_invites_composer import list_invites_composer
from modules.identity.application.composers.get_user_composer import get_user_composer
from modules.identity.application.composers.get_current_user_composer import get_current_user_composer
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/identity", tags=["identity"])


@router.get("/organizations")
async def list_organizations(request: FastAPIRequest):
    handler = list_organizations_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/users/me")
async def get_current_user(request: FastAPIRequest):
    handler = get_current_user_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/auth/login")
async def login(request: FastAPIRequest):
    handler = login_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/auth/register")
async def register(request: FastAPIRequest):
    handler = register_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


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
