from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest
from fastapi.responses import JSONResponse

from modules.identity.application.authentication_service import AuthenticationService
from modules.identity.application.dtos import LoginInput, RegisterInput
from modules.identity.application.composers.create_user_composer import create_user_composer
from modules.identity.application.composers.create_organization_composer import create_organization_composer
from modules.identity.application.composers.add_member_composer import add_member_composer
from modules.identity.application.composers.get_organization_composer import get_organization_composer
from modules.identity.application.composers.update_organization_composer import update_organization_composer
from modules.identity.application.composers.list_members_composer import list_members_composer
from modules.identity.application.composers.create_invite_composer import create_invite_composer
from modules.identity.application.composers.list_invites_composer import list_invites_composer
from modules.identity.application.composers.get_user_composer import get_user_composer
from shared.infra.errors import AuthenticationError
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/identity", tags=["identity"])


def _authentication_service(request: FastAPIRequest) -> AuthenticationService:
    return AuthenticationService(
        request.app.state.session_factory,
        request.app.state.access_token_codec,
        request.app.state.settings,
    )


def _auth_response(
    request: FastAPIRequest,
    result,
    *,
    status_code: int,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": "ok" if status_code == 200 else "created",
            "data": {
                "access_token": result.access_token,
                "token": result.access_token,
                "token_type": result.token_type,
                "expires_in": result.expires_in,
                "user": {
                    "id": str(result.user.id),
                    "email": result.user.email,
                    "status": result.user.status,
                },
            },
        },
    )
    settings = request.app.state.settings
    max_age = settings.refresh_token_ttl_days * 86400
    cookie_options = {
        "max_age": max_age,
        "httponly": True,
        "secure": settings.refresh_cookie_secure,
        "samesite": settings.refresh_cookie_same_site,
        "path": "/identity/auth",
    }
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=result.refresh_token,
        **cookie_options,
    )
    response.set_cookie(
        key=f"{settings.refresh_cookie_name}_session",
        value=str(result.session_id),
        **cookie_options,
    )
    return response


def _clear_auth_cookies(request: FastAPIRequest, response: JSONResponse) -> None:
    settings = request.app.state.settings
    options = {
        "path": "/identity/auth",
        "httponly": True,
        "secure": settings.refresh_cookie_secure,
        "samesite": settings.refresh_cookie_same_site,
    }
    response.delete_cookie(key=settings.refresh_cookie_name, **options)
    response.delete_cookie(
        key=f"{settings.refresh_cookie_name}_session",
        **options,
    )


@router.get("/organizations")
async def list_organizations(request: FastAPIRequest):
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise AuthenticationError("Authentication required")
    organizations = await _authentication_service(request).list_organizations(
        principal.user_id
    )
    return JSONResponse(
        content={
            "success": True,
            "message": "ok",
            "data": [
                {
                    "id": str(organization.id),
                    "name": organization.name,
                    "slug": organization.slug,
                    "status": organization.status.value,
                    "created_at": organization.created_at.isoformat()
                    if organization.created_at
                    else None,
                }
                for organization in organizations
            ],
        }
    )


@router.get("/users/me")
async def get_current_user(request: FastAPIRequest):
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise AuthenticationError("Authentication required")
    user = await _authentication_service(request).get_user(principal.user_id)
    return JSONResponse(
        content={
            "success": True,
            "message": "ok",
            "data": {
                "id": str(user.id),
                "email": user.email,
                "status": user.status,
            },
        }
    )


@router.post("/auth/login")
async def login(request: FastAPIRequest):
    data = LoginInput(**(await request.json()))
    result = await _authentication_service(request).login(
        email=data.email,
        password=data.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    return _auth_response(request, result, status_code=200)


@router.post("/auth/register")
async def register(request: FastAPIRequest):
    data = RegisterInput(**(await request.json()))
    result = await _authentication_service(request).register(
        email=data.email,
        password=data.password,
        organization_name=data.organization_name,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    return _auth_response(request, result, status_code=201)


@router.post("/auth/refresh")
async def refresh(request: FastAPIRequest):
    settings = request.app.state.settings
    secret = request.cookies.get(settings.refresh_cookie_name)
    session_value = request.cookies.get(f"{settings.refresh_cookie_name}_session")
    if not secret or not session_value:
        raise AuthenticationError("Invalid refresh session")
    try:
        session_id = UUID(session_value)
    except ValueError as exc:
        raise AuthenticationError("Invalid refresh session") from exc
    result = await _authentication_service(request).refresh(
        session_id=session_id,
        secret=secret,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    return _auth_response(request, result, status_code=200)


@router.post("/auth/logout")
async def logout(request: FastAPIRequest):
    settings = request.app.state.settings
    secret = request.cookies.get(settings.refresh_cookie_name)
    session_value = request.cookies.get(f"{settings.refresh_cookie_name}_session")
    session_id = None
    if session_value:
        try:
            session_id = UUID(session_value)
        except ValueError:
            session_id = None
    await _authentication_service(request).logout(
        session_id=session_id,
        secret=secret,
    )
    response = JSONResponse(
        content={"success": True, "message": "logged out", "data": None}
    )
    _clear_auth_cookies(request, response)
    return response


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
