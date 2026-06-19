from uuid import UUID

from fastapi import Request as FastAPIRequest
from fastapi.responses import JSONResponse

from modules.identity.application.authentication_service import AuthenticationService
from modules.identity.application.dtos import LoginInput, RegisterInput
from shared.infra.errors import AuthenticationError


def authentication_service(request: FastAPIRequest) -> AuthenticationService:
    return AuthenticationService(
        request.app.state.session_factory,
        request.app.state.access_token_codec,
        request.app.state.settings,
    )


def authentication_response(
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


def clear_auth_cookies(request: FastAPIRequest, response: JSONResponse) -> None:
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


async def list_organizations_endpoint(request: FastAPIRequest) -> JSONResponse:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise AuthenticationError("Authentication required")
    organizations = await authentication_service(request).list_organizations(
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


async def get_current_user_endpoint(request: FastAPIRequest) -> JSONResponse:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise AuthenticationError("Authentication required")
    user = await authentication_service(request).get_user(principal.user_id)
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


async def login_endpoint(request: FastAPIRequest) -> JSONResponse:
    data = LoginInput(**(await request.json()))
    result = await authentication_service(request).login(
        email=data.email,
        password=data.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    return authentication_response(request, result, status_code=200)


async def register_endpoint(request: FastAPIRequest) -> JSONResponse:
    data = RegisterInput(**(await request.json()))
    result = await authentication_service(request).register(
        email=data.email,
        password=data.password,
        organization_name=data.organization_name,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    return authentication_response(request, result, status_code=201)


async def refresh_endpoint(request: FastAPIRequest) -> JSONResponse:
    settings = request.app.state.settings
    secret = request.cookies.get(settings.refresh_cookie_name)
    session_value = request.cookies.get(f"{settings.refresh_cookie_name}_session")
    if not secret or not session_value:
        raise AuthenticationError("Invalid refresh session")
    try:
        session_id = UUID(session_value)
    except ValueError as exc:
        raise AuthenticationError("Invalid refresh session") from exc
    result = await authentication_service(request).refresh(
        session_id=session_id,
        secret=secret,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    return authentication_response(request, result, status_code=200)


async def logout_endpoint(request: FastAPIRequest) -> JSONResponse:
    settings = request.app.state.settings
    secret = request.cookies.get(settings.refresh_cookie_name)
    session_value = request.cookies.get(f"{settings.refresh_cookie_name}_session")
    session_id = None
    if session_value:
        try:
            session_id = UUID(session_value)
        except ValueError:
            session_id = None
    await authentication_service(request).logout(
        session_id=session_id,
        secret=secret,
    )
    response = JSONResponse(
        content={"success": True, "message": "logged out", "data": None}
    )
    clear_auth_cookies(request, response)
    return response
