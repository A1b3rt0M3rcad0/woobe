from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from hmac import compare_digest
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.errors import AuthenticationError, AuthorizationError
from shared.security.access_tokens import AccessTokenCodec
from shared.security.api_keys import hash_api_key, parse_project_api_key
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal
from shared.security.rate_limit import ApiKeyRequestLimiter
from shared.security.tenancy import TenantAuthorizer


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SqlSecurityAuthenticator:
    """SQL-backed implementation of the transport-neutral security contract."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        token_codec: AccessTokenCodec,
        api_key_rate_limiter: ApiKeyRequestLimiter,
    ) -> None:
        self._session_factory = session_factory
        self._token_codec = token_codec
        self._api_key_rate_limiter = api_key_rate_limiter

    async def authenticate_user(
        self,
        *,
        access_token: str,
        path_params: Mapping[str, Any],
        query_params: Mapping[str, Any],
        body: Any,
    ) -> AuthenticatedPrincipal:
        principal = self._token_codec.decode(access_token)
        async with self._session_factory() as session:
            await self._require_active_session(session, principal)
            await TenantAuthorizer(session).authorize(
                user_id=principal.user_id,
                path_params=path_params,
                query_params=query_params,
                body=body,
            )
        return principal

    async def authenticate_api_key(
        self,
        *,
        credentials: str,
        required_scope: str | None,
        runtime_interface: str | None,
        path_params: Mapping[str, Any],
        query_params: Mapping[str, Any],
        body: Any,
    ) -> ProjectApiPrincipal:
        parsed = parse_project_api_key(credentials)
        if parsed is None:
            raise AuthenticationError("Invalid API key")
        if required_scope is None:
            raise AuthorizationError("API key access is not allowed for this endpoint")

        supplied_digest = hash_api_key(credentials)
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, project_id, key_prefix, key_hash, key_version,
                           scopes, kind, agent_id, target_type, target_id,
                           environment, interfaces,
                           status, revoked_at, expires_at
                    FROM core.api_keys
                    WHERE key_prefix = :key_prefix
                      AND key_version = :key_version
                    """
                ),
                {
                    "key_prefix": parsed.public_prefix,
                    "key_version": parsed.key_version,
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

            key_kind = str(matching_row.kind or "project")
            key_environment = (
                str(matching_row.environment)
                if matching_row.environment is not None
                else None
            )
            if not parsed.matches_binding(
                kind=key_kind,
                environment=key_environment,
            ):
                raise AuthenticationError("Invalid API key")

            interfaces = frozenset(
                str(interface) for interface in (matching_row.interfaces or [])
            )
            if runtime_interface is not None:
                if key_kind != "runtime":
                    raise AuthorizationError(
                        "A Runtime Key is required for this endpoint"
                    )
                target_type = (
                    str(matching_row.target_type)
                    if matching_row.target_type is not None
                    else "agent"
                    if matching_row.agent_id is not None
                    else None
                )
                target_id = matching_row.target_id or matching_row.agent_id
                if (
                    target_type not in {"agent", "network"}
                    or target_id is None
                    or key_environment is None
                ):
                    raise AuthorizationError("Runtime Key binding is incomplete")
                if (
                    runtime_interface != "contract"
                    and runtime_interface not in interfaces
                ):
                    raise AuthorizationError(
                        "Runtime Key is not allowed to use this interface"
                    )
            elif key_kind == "runtime":
                raise AuthorizationError(
                    "Runtime Keys can only access the public runtime API"
                )

            principal = ProjectApiPrincipal(
                api_key_id=UUID(str(matching_row.id)),
                project_id=UUID(str(matching_row.project_id)),
                key_prefix=parsed.display_prefix,
                scopes=scopes,
                kind=key_kind,
                agent_id=(
                    UUID(str(matching_row.agent_id))
                    if matching_row.agent_id is not None
                    else None
                ),
                target_type=(
                    str(matching_row.target_type)
                    if matching_row.target_type is not None
                    else "agent"
                    if matching_row.agent_id is not None
                    else None
                ),
                target_id=(
                    UUID(str(matching_row.target_id or matching_row.agent_id))
                    if (
                        matching_row.target_id is not None
                        or matching_row.agent_id is not None
                    )
                    else None
                ),
                environment=key_environment,
                interfaces=interfaces,
                authenticated_at=now,
            )
            if key_kind != "runtime":
                await TenantAuthorizer(session).authorize_api_key(
                    project_id=principal.project_id,
                    path_params=path_params,
                    query_params=query_params,
                    body=body,
                )
            await self._api_key_rate_limiter.consume(str(principal.api_key_id))
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
