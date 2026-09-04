from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from hmac import compare_digest
from typing import Any
from uuid import UUID

from fastapi import Request

from shared.infra.config import Settings
from shared.infra.errors import (
    AuthenticationError,
    AuthorizationError,
    PayloadTooLargeError,
)
from shared.security.api_keys import (
    API_KEY_SCOPE_RUNTIME_EXECUTE,
    API_KEY_SCOPE_TRACES_READ,
    API_KEY_SCOPE_USAGE_READ,
    is_api_key_candidate,
)
from shared.security.authentication import SecurityAuthenticator
from shared.security.principal import (
    ProjectApiPrincipal,
    SecurityPrincipal,
)
from shared.security.rate_limit import (
    ApiKeyConcurrencyLimiter,
    LoginRateLimiter,
)

PUBLIC_PATHS = {
    "/identity/auth/login",
    "/identity/auth/logout",
    "/identity/auth/register",
    "/identity/auth/refresh",
    "/identity/instance/status",
    "/identity/instance/bootstrap",
}
_LOCAL_ENVIRONMENTS = {"development", "dev", "test", "local"}
_ALLOWED_SAME_SITE = {"lax", "strict", "none"}
_CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _is_public_run_cancel(method: str, path: str) -> bool:
    return (
        method.upper() == "POST"
        and path.startswith("/v1/runs/")
        and path.endswith("/cancel")
    )


def public_runtime_interface(method: str, path: str) -> str | None:
    normalized_method = method.upper()
    if normalized_method == "POST" and path == "/v1/run":
        return "http"
    if normalized_method == "POST" and path == "/v1/run/stream":
        return "stream"
    if (
        normalized_method == "GET"
        and path.startswith("/v1/runs/")
        and path.endswith("/stream")
    ):
        return "stream"
    if _is_public_run_cancel(normalized_method, path):
        return "http"
    if (
        normalized_method == "GET"
        and path.startswith("/v1/sessions/")
        and path.endswith("/active-run")
    ):
        return "stream"
    if normalized_method == "POST" and path == "/v1/jobs":
        return "jobs"
    if normalized_method == "GET" and path.startswith("/v1/jobs/"):
        return "jobs"
    return None


def is_runtime_path(path: str) -> bool:
    return (
        path.startswith("/runtime/")
        or path.startswith("/agent/runtime/")
        or path == "/v1/run"
        or path == "/v1/run/stream"
        or path == "/v1/jobs"
        or path.startswith("/v1/jobs/")
        or (
            path.startswith("/v1/runs/")
            and (path.endswith("/stream") or path.endswith("/cancel"))
        )
        or (
            path.startswith("/v1/sessions/")
            and path.endswith("/active-run")
        )
    )


def is_chat_surface_public_path(path: str) -> bool:
    return path.startswith("/v1/chat-surfaces/") or path.startswith("/v1/chat/")


def is_runtime_execution_request(method: str, path: str) -> bool:
    if path.startswith("/runtime/") or path.startswith("/agent/runtime/"):
        return True
    if _is_public_run_cancel(method, path):
        return False
    interface = public_runtime_interface(method, path)
    if method.upper() == "GET" and interface == "stream":
        return False
    return interface in {"http", "stream"} or (
        interface == "jobs" and method.upper() == "POST"
    )


def _validate_runtime_security_settings(settings: Settings) -> None:
    environment = settings.environment.strip().lower()
    cookie_settings = (
        (
            "access",
            bool(settings.access_cookie_secure),
            settings.access_cookie_same_site,
        ),
        (
            "refresh",
            bool(settings.refresh_cookie_secure),
            settings.refresh_cookie_same_site,
        ),
    )

    for name, secure, same_site_value in cookie_settings:
        same_site = str(same_site_value).strip().lower()
        if same_site not in _ALLOWED_SAME_SITE:
            raise ValueError(f"Invalid {name} cookie same-site policy")
        if environment not in _LOCAL_ENVIRONMENTS and not secure:
            raise ValueError(f"Production {name} cookies require transport security")
        if same_site == "none" and not secure:
            raise ValueError(f"Cross-site {name} cookies require transport security")


def _required_api_key_scope(method: str, path: str) -> str | None:
    if is_runtime_path(path):
        return API_KEY_SCOPE_RUNTIME_EXECUTE
    if method == "GET" and path.startswith("/observability/traces"):
        return API_KEY_SCOPE_TRACES_READ
    if method == "GET" and path.startswith("/metering/"):
        return API_KEY_SCOPE_USAGE_READ
    return None


def _values_for_key(value: Any, target: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) == target:
                found.append(item)
            if isinstance(item, (Mapping, list, tuple)):
                found.extend(_values_for_key(item, target))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_values_for_key(item, target))
    return found


def _serialized_size(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":"), default=str).encode("utf-8"))


class HttpSecurityGuard:
    def __init__(
        self,
        *,
        authenticator: SecurityAuthenticator,
        login_rate_limiter: LoginRateLimiter,
        api_key_concurrency_limiter: ApiKeyConcurrencyLimiter,
        settings: Settings,
    ) -> None:
        _validate_runtime_security_settings(settings)
        self._authenticator = authenticator
        self._login_rate_limiter = login_rate_limiter
        self._api_key_concurrency_limiter = api_key_concurrency_limiter
        self._settings = settings

    @property
    def runtime_timeout_seconds(self) -> float:
        return self._settings.runtime_total_timeout_seconds

    def requires_runtime_permit(
        self,
        request: Request,
        principal: SecurityPrincipal | None,
    ) -> bool:
        return isinstance(
            principal, ProjectApiPrincipal
        ) and is_runtime_execution_request(request.method, request.url.path)

    async def acquire_runtime_permit(self, principal: ProjectApiPrincipal) -> UUID:
        return await self._api_key_concurrency_limiter.acquire(
            str(principal.api_key_id)
        )

    async def release_runtime_permit(self, lease_id: UUID) -> None:
        await self._api_key_concurrency_limiter.release(lease_id)

    async def authenticate_and_authorize(
        self,
        request: Request,
        *,
        body: Any,
        query_params: dict[str, Any],
        path_params: dict[str, Any],
    ) -> SecurityPrincipal | None:
        if request.method == "OPTIONS":
            return None

        path = request.url.path
        if path == "/identity/auth/login":
            client = request.client.host if request.client else "unknown"
            await self._login_rate_limiter.consume(client)

        if path in PUBLIC_PATHS or is_chat_surface_public_path(path):
            return None

        if is_runtime_path(path):
            self._validate_runtime_payload(request, body)

        authorization = request.headers.get("authorization", "")
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() == "bearer" and credentials:
            if is_api_key_candidate(credentials):
                return await self._authenticate_api_key(
                    request=request,
                    credentials=credentials,
                    body=body,
                    query_params=query_params,
                    path_params=path_params,
                )
            access_token = credentials
            token_source = "header"
        else:
            access_token = request.cookies.get(self._settings.access_cookie_name)
            token_source = "cookie"

        if not access_token:
            raise AuthenticationError("Authentication required")

        principal = await self._authenticator.authenticate_user(
            access_token=access_token,
            path_params=path_params,
            query_params=query_params,
            body=body,
        )

        if token_source == "cookie":
            self._validate_csrf(request)

        return principal

    async def _authenticate_api_key(
        self,
        *,
        request: Request,
        credentials: str,
        body: Any,
        query_params: dict[str, Any],
        path_params: dict[str, Any],
    ) -> ProjectApiPrincipal:
        required_scope = _required_api_key_scope(request.method, request.url.path)
        return await self._authenticator.authenticate_api_key(
            credentials=credentials,
            required_scope=required_scope,
            runtime_interface=public_runtime_interface(
                request.method,
                request.url.path,
            ),
            path_params=path_params,
            query_params=query_params,
            body=body,
        )

    def _validate_csrf(self, request: Request) -> None:
        if request.method.upper() not in _CSRF_METHODS:
            return

        csrf_cookie = request.cookies.get(self._settings.csrf_cookie_name)
        csrf_header = request.headers.get(self._settings.csrf_header_name)
        if not csrf_cookie or not csrf_header:
            raise AuthorizationError("CSRF validation failed")
        if not compare_digest(csrf_cookie, csrf_header):
            raise AuthorizationError("CSRF validation failed")

    def _validate_runtime_payload(self, request: Request, body: Any) -> None:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self._settings.runtime_max_request_bytes:
                    raise PayloadTooLargeError("Runtime request body is too large")
            except ValueError:
                raise PayloadTooLargeError("Invalid Content-Length header") from None

        if body is None:
            return
        if _serialized_size(body) > self._settings.runtime_max_request_bytes:
            raise PayloadTooLargeError("Runtime request body is too large")

        for key in ("message", "prompt"):
            for value in _values_for_key(body, key):
                if (
                    isinstance(value, str)
                    and len(value) > self._settings.runtime_max_prompt_chars
                ):
                    raise PayloadTooLargeError("Runtime prompt is too large")

        for value in _values_for_key(body, "metadata"):
            if _serialized_size(value) > self._settings.runtime_max_metadata_bytes:
                raise PayloadTooLargeError("Runtime metadata is too large")

        for value in _values_for_key(body, "snapshot_override"):
            if (
                _serialized_size(value)
                > self._settings.runtime_max_snapshot_override_bytes
            ):
                raise PayloadTooLargeError("Runtime snapshot override is too large")
