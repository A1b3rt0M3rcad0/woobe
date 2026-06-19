from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.errors import AuthenticationError
from shared.security.access_tokens import AccessTokenCodec
from shared.security.principal import AuthenticatedPrincipal
from shared.security.rate_limit import LoginRateLimiter
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


class HttpSecurityGuard:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        token_codec: AccessTokenCodec,
        login_rate_limiter: LoginRateLimiter,
    ) -> None:
        self._session_factory = session_factory
        self._token_codec = token_codec
        self._login_rate_limiter = login_rate_limiter

    async def authenticate_and_authorize(
        self,
        request: Request,
        *,
        body: Any,
        query_params: dict[str, Any],
        path_params: dict[str, Any],
    ) -> AuthenticatedPrincipal | None:
        if request.method == "OPTIONS":
            return None

        path = request.url.path
        if path == "/identity/auth/login":
            client = request.client.host if request.client else "unknown"
            self._login_rate_limiter.consume(client)

        if path in PUBLIC_PATHS:
            return None

        authorization = request.headers.get("authorization", "")
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() != "bearer" or not credentials:
            raise AuthenticationError("Authentication required")

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
