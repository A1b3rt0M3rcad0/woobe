from secrets import token_urlsafe
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import Request as FastAPIRequest
from fastapi.responses import JSONResponse

from modules.identity.application.authentication_service import AuthenticationService
from modules.identity.application.dtos import LoginInput, RegisterInput
from shared.infra.errors import AuthenticationError


ACCESS_COOKIE_PATH = "/"
CSRF_COOKIE_PATH = "/"
REFRESH_COOKIE_PATH = "/identity/auth"


def authentication_service(request: FastAPIRequest) -> AuthenticationService:
    return AuthenticationService(
        request.app.state.session_factory,
        request.app.state.access_token_codec,
        request.app.state.settings,
    )


def browser_request_is_secure(request: FastAPIRequest) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    origin = request.headers.get("origin", "")
    return (
        request.url.scheme == "https"
        or forwarded_proto.split(",")[0].strip() == "https"
        or urlsplit(origin).scheme == "https"
    )


def request_is_cross_origin(request: FastAPIRequest) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return False
    origin_host = urlsplit(origin).netloc
    request_host = request.headers.get("host", "")
    return bool(origin_host and request_host and origin_host != request_host)


def browser_cookie_policy(
    request: FastAPIRequest,
    *,
    secure: bool,
    same_site: str,
) -> tuple[bool, str]:
    if request_is_cross_origin(request) and browser_request_is_secure(request):
        return True, "none"
    return secure, same_site


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
    refresh_max_age = settings.refresh_token_ttl_days * 86400
    access_max_age = min(result.expires_in, settings.access_token_ttl_seconds)
    access_secure, access_same_site = browser_cookie_policy(
        request,
        secure=settings.access_cookie_secure,
        same_site=settings.access_cookie_same_site,
    )
    refresh_secure, refresh_same_site = browser_cookie_policy(
        request,
        secure=settings.refresh_cookie_secure,
        same_site=settings.refresh_cookie_same_site,
    )

    response.set_cookie(
        key=settings.access_cookie_name,
        value=result.access_token,
        max_age=access_max_age,
        httponly=True,
        secure=access_secure,
        samesite=access_same_site,
        path=ACCESS_COOKIE_PATH,
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token_urlsafe(32),
        max_age=refresh_max_age,
        httponly=False,
        secure=access_secure,
        samesite=access_same_site,
        path=CSRF_COOKIE_PATH,
    )

    refresh_cookie_options = {
        "max_age": refresh_max_age,
        "httponly": True,
        "secure": refresh_secure,
        "samesite": refresh_same_site,
        "path": REFRESH_COOKIE_PATH,
    }
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=result.refresh_token,
        **refresh_cookie_options,
    )
    response.set_cookie(
        key=f"{settings.refresh_cookie_name}_session",
        value=str(result.session_id),
        **refresh_cookie_options,
    )
    return response


def clear_auth_cookies(request: FastAPIRequest, response: JSONResponse) -> None:
    settings = request.app.state.settings
    access_secure, access_same_site = browser_cookie_policy(
        request,
        secure=settings.access_cookie_secure,
        same_site=settings.access_cookie_same_site,
    )
    refresh_secure, refresh_same_site = browser_cookie_policy(
        request,
        secure=settings.refresh_cookie_secure,
        same_site=settings.refresh_cookie_same_site,
    )
    response.delete_cookie(
        key=settings.access_cookie_name,
        path=ACCESS_COOKIE_PATH,
        httponly=True,
        secure=access_secure,
        samesite=access_same_site,
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path=CSRF_COOKIE_PATH,
        httponly=False,
        secure=access_secure,
        samesite=access_same_site,
    )

    refresh_cookie_options = {
        "path": REFRESH_COOKIE_PATH,
        "httponly": True,
        "secure": refresh_secure,
        "samesite": refresh_same_site,
    }
    response.delete_cookie(key=settings.refresh_cookie_name, **refresh_cookie_options)
    response.delete_cookie(
        key=f"{settings.refresh_cookie_name}_session",
        **refresh_cookie_options,
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
