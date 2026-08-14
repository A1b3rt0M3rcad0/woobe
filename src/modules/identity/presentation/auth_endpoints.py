from secrets import token_urlsafe
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import Request as FastAPIRequest
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from modules.identity.application.authentication_service import AuthenticationService
from modules.identity.application.dtos import CreateWorkspaceInput, LoginInput, RegisterInput
from shared.infra.errors import AuthenticationError


ACCESS_COOKIE_PATH = "/"
CSRF_COOKIE_PATH = "/"
REFRESH_COOKIE_PATH = "/identity/auth"
CSRF_RESPONSE_HEADER = "X-CSRF-Token"


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


def set_csrf_cookie(
    request: FastAPIRequest,
    response: JSONResponse,
    *,
    csrf_value: str,
    max_age: int,
) -> None:
    settings = request.app.state.settings
    access_secure, access_same_site = browser_cookie_policy(
        request,
        secure=settings.access_cookie_secure,
        same_site=settings.access_cookie_same_site,
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_value,
        max_age=max_age,
        httponly=False,
        secure=access_secure,
        samesite=access_same_site,
        path=CSRF_COOKIE_PATH,
    )
    response.headers[CSRF_RESPONSE_HEADER] = csrf_value


def workspace_payload(workspace) -> dict:
    return {
        "id": str(workspace.id),
        "name": workspace.name,
        "slug": workspace.slug,
        "status": workspace.status.value
        if hasattr(workspace.status, "value")
        else workspace.status,
        "created_at": workspace.created_at.isoformat()
        if getattr(workspace, "created_at", None)
        else None,
    }


def authentication_response(
    request: FastAPIRequest,
    result,
    *,
    status_code: int,
) -> JSONResponse:
    csrf_value = token_urlsafe(32)
    response_data = {
        "token_type": result.token_type,
        "expires_in": result.expires_in,
        "csrf": csrf_value,
        "user": {
            "id": str(result.user.id),
            "email": result.user.email,
            "status": result.user.status,
        },
    }
    if result.workspace is not None:
        response_data["workspace"] = workspace_payload(result.workspace)

    response = JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": "ok" if status_code == 200 else "created",
            "data": response_data,
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
    set_csrf_cookie(
        request,
        response,
        csrf_value=csrf_value,
        max_age=refresh_max_age,
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


async def list_workspaces_endpoint(request: FastAPIRequest) -> JSONResponse:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise AuthenticationError("Authentication required")
    workspaces = await authentication_service(request).list_workspaces(
        principal.user_id
    )
    return JSONResponse(
        content={
            "success": True,
            "message": "ok",
            "data": jsonable_encoder(workspaces),
        }
    )


async def create_workspace_endpoint(request: FastAPIRequest) -> JSONResponse:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise AuthenticationError("Authentication required")
    data = CreateWorkspaceInput(**(await request.json()))
    workspace = await authentication_service(request).create_workspace(
        user_id=principal.user_id,
        name=data.name,
        slug=data.slug,
    )
    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "message": "created",
            "data": workspace_payload(workspace),
        },
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


async def csrf_endpoint(request: FastAPIRequest) -> JSONResponse:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise AuthenticationError("Authentication required")
    settings = request.app.state.settings
    csrf_value = token_urlsafe(32)
    response = JSONResponse(
        content={
            "success": True,
            "message": "ok",
            "data": {"csrf": csrf_value},
        }
    )
    set_csrf_cookie(
        request,
        response,
        csrf_value=csrf_value,
        max_age=settings.refresh_token_ttl_days * 86400,
    )
    return response


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
