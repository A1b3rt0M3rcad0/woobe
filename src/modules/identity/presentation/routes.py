from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest

from modules.identity.application.composers.add_member_composer import add_member_composer
from modules.identity.application.composers.create_invite_composer import (
    create_invite_composer,
)
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
    authentication_service,
    create_organization_endpoint,
    csrf_endpoint,
    get_current_user_endpoint,
    list_organizations_endpoint,
    login_endpoint,
    logout_endpoint,
    organization_payload,
    refresh_endpoint,
    register_endpoint,
)
from shared.infra.errors import AuthenticationError, AuthorizationError, NotFoundError, ValidationError
from shared.presentation.http.adapter import request_adapter, response_adapter
from shared.security.organization_access import OrganizationAccessService


router = APIRouter(prefix="/identity", tags=["identity"])


def _principal_user_id(request: FastAPIRequest) -> UUID:
    principal = getattr(request.state, "principal", None)
    user_id = getattr(principal, "user_id", None)
    if user_id is None:
        raise AuthenticationError("Authentication required")
    return UUID(str(user_id))


def _organization_access(request: FastAPIRequest) -> OrganizationAccessService:
    return OrganizationAccessService(request.app.state.session_factory)


def _uuid(value: str, field: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid {field}") from exc


@router.get("/organizations")
async def list_organizations(request: FastAPIRequest):
    return await list_organizations_endpoint(request)


@router.get("/invites/pending")
async def list_pending_invites(request: FastAPIRequest):
    invites = await authentication_service(request).list_pending_invites(
        _principal_user_id(request)
    )
    return {"success": True, "message": "ok", "data": invites}


@router.post("/invites/{invite_id}/accept")
async def accept_invite(request: FastAPIRequest, invite_id: UUID):
    organization = await authentication_service(request).accept_invite(
        user_id=_principal_user_id(request),
        invite_id=invite_id,
    )
    return {
        "success": True,
        "message": "accepted",
        "data": organization_payload(organization),
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


@router.post("/organizations")
async def create_organization(request: FastAPIRequest):
    return await create_organization_endpoint(request)


@router.post("/organizations/{org_id}/members")
async def add_member(request: FastAPIRequest, org_id: str):
    organization_id = _uuid(org_id, "organization id")
    payload = dict(await request.json())
    role = payload.get("role", "member")
    if not isinstance(role, str):
        raise ValidationError("Invalid member role")
    await _organization_access(request).require_role_assignment(
        actor_user_id=_principal_user_id(request),
        organization_id=organization_id,
        target_role=role,
    )
    handler = add_member_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/organizations/{org_id}")
async def get_organization(request: FastAPIRequest, org_id: str):
    del org_id
    handler = get_organization_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/organizations/{org_id}")
async def update_organization(request: FastAPIRequest, org_id: str):
    await _organization_access(request).require_admin(
        _principal_user_id(request),
        _uuid(org_id, "organization id"),
    )
    handler = update_organization_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/organizations/{org_id}/members")
async def list_members(request: FastAPIRequest, org_id: str):
    del org_id
    handler = list_members_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/organizations/{org_id}/invites")
async def create_invite(request: FastAPIRequest, org_id: str):
    principal_user_id = _principal_user_id(request)
    payload = dict(await request.json())
    role = payload.get("role", "member")
    if not isinstance(role, str):
        raise ValidationError("Invalid invite role")
    await _organization_access(request).require_role_assignment(
        actor_user_id=principal_user_id,
        organization_id=_uuid(org_id, "organization id"),
        target_role=role,
    )
    handler = create_invite_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/organizations/{org_id}/invites")
async def list_invites(request: FastAPIRequest, org_id: str):
    del org_id
    handler = list_invites_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/users/{user_id}")
async def get_user(request: FastAPIRequest, user_id: str):
    target_user_id = _uuid(user_id, "user id")
    if _principal_user_id(request) != target_user_id:
        raise NotFoundError("User not found")
    handler = get_user_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
