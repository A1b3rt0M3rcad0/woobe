from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hmac import compare_digest
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.domain.enums import ApiKeyScope
from shared.infra.config import Settings
from shared.infra.errors import (
    AuthenticationError,
    AuthorizationError,
    PayloadTooLargeError,
)
from shared.security.access_tokens import AccessTokenCodec
from shared.security.api_keys import (
    API_KEY_VERSION,
    hash_api_key,
    parse_project_api_key,
)
from shared.security.principal import (
    AuthenticatedPrincipal,
    ProjectApiPrincipal,
    SecurityPrincipal,
)
from shared.security.rate_limit import (
    ApiKeyConcurrencyLimiter,
    ApiKeyRequestLimiter,
    LoginRateLimiter,
)
from shared.security.tenancy import TenantAuthorizer

PUBLIC_PATHS = {
    "/identity/auth/login",
    "/identity/auth/register",
    "/identity/auth/refresh",
}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_runtime_path(path: str) -> bool:
    return path.startswith("/runtime/") or path.startswith("/agent/runtime/")


def _required_api_key_scope(method: str, path: str) -> str | None:
    if _is_runtime_path(path):
        return ApiKeyScope.runtime_execute.value
    if method == "GET" and path.startswith("/observability/traces"):
        return ApiKeyScope.traces_read.value
    if method == "GET" and path.startswith("/metering/"):
        return ApiKeyScope.usage_read.value
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
    return len(
        json.dumps(value, separators=(",", ":"), default=str).encode("utf-8")
    )


class HttpSecurityGuard:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        token_codec: AccessTokenCodec,
        login_rate_limiter: LoginRateLimiter,
        api_key_rate_limiter: ApiKeyRequestLimiter,
        api_key_concurrency_limiter: ApiKeyConcurrencyLimiter,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._token_codec = token_codec
        self._login_rate_limiter = login_rate_limiter
        self._api_key_rate_limiter = api_key_rate_limiter
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
        return isinstance(principal, ProjectApiPrincipal) and _is_runtime_path(
            request.url.path
        )

    async def acquire_runtime_permit(self, principal: ProjectApiPrincipal) -> None:
        await self._api_key_concurrency_limiter.acquire(str(principal.api_key_id))

    async def release_runtime_permit(self, principal: ProjectApiPrincipal) -> None:
        await self._api_key_concurrency_limiter.release(str(principal.api_key_id))

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
            self._login_rate_limiter.consume(client)

        if path in PUBLIC_PATHS:
            return None

        if _is_runtime_path(path):
            self._validate_runtime_payload(request, body)

        authorization = request.headers.get("authorization", "")
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() != "bearer" or not credentials:
            raise AuthenticationError("Authentication required")

        if credentials.startswith("rai_live_"):
            return await self._authenticate_api_key(
                request=request,
                credentials=credentials,
                body=body,
                query_params=query_params,
                path_params=path_params,
            )

        principal = self._token_codec.decode(credentials)
        async with self._session_factory() as session:
            await self._require_active_session(session, principal)
            await TenantAuthorizer(session).authorize(
                user_id=principal.user_id,
                path_params=path_params,
                query_params=query_params,
                body=body,
            )
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
        parsed = parse_project_api_key(credentials)
        if parsed is None:
            raise AuthenticationError("Invalid API key")

        required_scope = _required_api_key_scope(request.method, request.url.path)
        if required_scope is None:
            raise AuthorizationError("API key access is not allowed for this endpoint")

        supplied_digest = hash_api_key(credentials)
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, project_id, key_prefix, key_hash, key_version,
                           scopes, status, revoked_at, expires_at
                    FROM core.api_keys
                    WHERE key_prefix = :key_prefix
                      AND key_version = :key_version
                    """
                ),
                {
                    "key_prefix": parsed.public_prefix,
                    "key_version": API_KEY_VERSION,
                },
            )
            matching_row = None
            for row in result.all():
                stored_hash = bytes(row.key_hash)
                if compare_digest(stored_hash, supplied_digest):
                    matching_row = row
                    break
            if matching_row is None:
                raise AuthenticationError("Invalid API key")

            expires_at = matching_row.expires_at
            if (
                matching_row.status != "active"
                or matching_row.revoked_at is not None
                or (expires_at is not None and _as_utc(expires_at) <= now)
            ):
                raise AuthenticationError("API key is inactive")

            scopes = frozenset(str(scope) for scope in (matching_row.scopes or []))
            if required_scope not in scopes:
                raise AuthorizationError("API key scope is not sufficient")

            principal = ProjectApiPrincipal(
                api_key_id=UUID(str(matching_row.id)),
                project_id=UUID(str(matching_row.project_id)),
                key_prefix=parsed.display_prefix,
                scopes=scopes,
                authenticated_at=now,
            )
            await TenantAuthorizer(session).authorize_api_key(
                project_id=principal.project_id,
                path_params=path_params,
                query_params=query_params,
                body=body,
            )
            self._api_key_rate_limiter.consume(str(principal.api_key_id))
            await session.execute(
                text(
                    """
                    UPDATE core.api_keys
                    SET last_used_at = :last_used_at,
                        updated_at = :last_used_at
                    WHERE id = :api_key_id
                    """
                ),
                {"last_used_at": now, "api_key_id": principal.api_key_id},
            )
            await session.commit()
            return principal

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
                if isinstance(value, str) and len(value) > self._settings.runtime_max_prompt_chars:
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

    async def _require_active_session(
        self,
        session: AsyncSession,
        principal: AuthenticatedPrincipal,
    ) -> None:
        result = await session.execute(
            text(
                """
                SELECT user_id, revoked_at, expires_at
                FROM identity.user_sessions
                WHERE id = :session_id
                """
            ),
            {"session_id": principal.session_id},
        )
        row = result.one_or_none()
        if row is None:
            raise AuthenticationError("Authentication session is invalid")

        user_id, revoked_at, expires_at = row
        if UUID(str(user_id)) != principal.user_id:
            raise AuthenticationError("Authentication session is invalid")
        if revoked_at is not None:
            raise AuthenticationError("Authentication session was revoked")
        if _as_utc(expires_at) <= datetime.now(UTC):
            raise AuthenticationError("Authentication session expired")
