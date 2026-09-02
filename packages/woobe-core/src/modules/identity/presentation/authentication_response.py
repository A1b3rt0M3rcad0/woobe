from dataclasses import dataclass
from secrets import token_urlsafe
from urllib.parse import urlsplit

from modules.identity.application.auth_types import IssuedAuthentication
from shared.presentation.http.request import Request
from shared.presentation.http.response import (
    DeleteResponseCookie,
    Response,
    ResponseCookie,
)


ACCESS_COOKIE_PATH = "/"
CSRF_COOKIE_PATH = "/"
REFRESH_COOKIE_PATH = "/identity/auth"
CSRF_RESPONSE_HEADER = "X-CSRF-Token"


@dataclass(frozen=True, slots=True)
class AuthenticationCookiePolicy:
    access_cookie_name: str
    access_cookie_secure: bool
    access_cookie_same_site: str
    refresh_cookie_name: str
    refresh_cookie_secure: bool
    refresh_cookie_same_site: str
    csrf_cookie_name: str
    refresh_token_ttl_days: int
    access_token_ttl_seconds: int


def _browser_request_is_secure(request: Request) -> bool:
    forwarded_proto = str(request.headers.get("x-forwarded-proto", ""))
    origin = str(request.headers.get("origin", ""))
    request_scheme = urlsplit(request.url or "").scheme
    return (
        request_scheme == "https"
        or forwarded_proto.split(",")[0].strip() == "https"
        or urlsplit(origin).scheme == "https"
    )


def _request_is_cross_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return False
    origin_host = urlsplit(str(origin)).netloc
    request_host = str(request.headers.get("host", ""))
    return bool(origin_host and request_host and origin_host != request_host)


def _browser_cookie_policy(
    request: Request,
    *,
    secure: bool,
    same_site: str,
) -> tuple[bool, str]:
    if _request_is_cross_origin(request) and _browser_request_is_secure(request):
        return True, "none"
    return secure, same_site


def _csrf_cookie(
    request: Request,
    policy: AuthenticationCookiePolicy,
    *,
    value: str,
) -> ResponseCookie:
    secure, same_site = _browser_cookie_policy(
        request,
        secure=policy.access_cookie_secure,
        same_site=policy.access_cookie_same_site,
    )
    return ResponseCookie(
        key=policy.csrf_cookie_name,
        value=value,
        max_age=policy.refresh_token_ttl_days * 86400,
        httponly=False,
        secure=secure,
        samesite=same_site,
        path=CSRF_COOKIE_PATH,
    )


def authentication_response(
    request: Request,
    result: IssuedAuthentication,
    policy: AuthenticationCookiePolicy,
    *,
    status_code: int,
) -> Response:
    csrf_value = token_urlsafe(32)
    data: dict[str, object] = {
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
        data["workspace"] = {
            "id": str(result.workspace.id),
            "name": result.workspace.name,
            "slug": result.workspace.slug,
            "status": result.workspace.status,
        }

    access_secure, access_same_site = _browser_cookie_policy(
        request,
        secure=policy.access_cookie_secure,
        same_site=policy.access_cookie_same_site,
    )
    refresh_secure, refresh_same_site = _browser_cookie_policy(
        request,
        secure=policy.refresh_cookie_secure,
        same_site=policy.refresh_cookie_same_site,
    )
    refresh_max_age = policy.refresh_token_ttl_days * 86400
    return Response(
        status_code=status_code,
        body={
            "success": True,
            "message": "ok" if status_code == 200 else "created",
            "data": data,
        },
        headers={CSRF_RESPONSE_HEADER: csrf_value},
        cookies=[
            ResponseCookie(
                key=policy.access_cookie_name,
                value=result.access_token,
                max_age=min(result.expires_in, policy.access_token_ttl_seconds),
                httponly=True,
                secure=access_secure,
                samesite=access_same_site,
                path=ACCESS_COOKIE_PATH,
            ),
            _csrf_cookie(request, policy, value=csrf_value),
            ResponseCookie(
                key=policy.refresh_cookie_name,
                value=result.refresh_token,
                max_age=refresh_max_age,
                httponly=True,
                secure=refresh_secure,
                samesite=refresh_same_site,
                path=REFRESH_COOKIE_PATH,
            ),
            ResponseCookie(
                key=f"{policy.refresh_cookie_name}_session",
                value=str(result.session_id),
                max_age=refresh_max_age,
                httponly=True,
                secure=refresh_secure,
                samesite=refresh_same_site,
                path=REFRESH_COOKIE_PATH,
            ),
        ],
    )


def csrf_response(request: Request, policy: AuthenticationCookiePolicy) -> Response:
    csrf_value = token_urlsafe(32)
    return Response(
        status_code=200,
        body={
            "success": True,
            "message": "ok",
            "data": {"csrf": csrf_value},
        },
        headers={CSRF_RESPONSE_HEADER: csrf_value},
        cookies=[_csrf_cookie(request, policy, value=csrf_value)],
    )


def logout_response(request: Request, policy: AuthenticationCookiePolicy) -> Response:
    access_secure, access_same_site = _browser_cookie_policy(
        request,
        secure=policy.access_cookie_secure,
        same_site=policy.access_cookie_same_site,
    )
    refresh_secure, refresh_same_site = _browser_cookie_policy(
        request,
        secure=policy.refresh_cookie_secure,
        same_site=policy.refresh_cookie_same_site,
    )
    return Response(
        status_code=200,
        body={"success": True, "message": "logged out", "data": None},
        delete_cookies=[
            DeleteResponseCookie(
                key=policy.access_cookie_name,
                httponly=True,
                secure=access_secure,
                samesite=access_same_site,
                path=ACCESS_COOKIE_PATH,
            ),
            DeleteResponseCookie(
                key=policy.csrf_cookie_name,
                httponly=False,
                secure=access_secure,
                samesite=access_same_site,
                path=CSRF_COOKIE_PATH,
            ),
            DeleteResponseCookie(
                key=policy.refresh_cookie_name,
                httponly=True,
                secure=refresh_secure,
                samesite=refresh_same_site,
                path=REFRESH_COOKIE_PATH,
            ),
            DeleteResponseCookie(
                key=f"{policy.refresh_cookie_name}_session",
                httponly=True,
                secure=refresh_secure,
                samesite=refresh_same_site,
                path=REFRESH_COOKIE_PATH,
            ),
        ],
    )
