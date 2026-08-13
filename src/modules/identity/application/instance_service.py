from __future__ import annotations

from datetime import UTC, datetime

import uuid6
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.application.auth_types import AuthenticatedUser, IssuedAuthentication
from modules.identity.application.session_lifecycle import SessionLifecycle
from modules.identity.domain.entities import User
from modules.identity.domain.errors import EmailAlreadyExistsError
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from shared.infra.config import Settings
from shared.infra.crypto import hash_password
from shared.infra.errors import AuthorizationError, ConflictError
from shared.security.access_tokens import AccessTokenCodec


class InstanceService:
    """Lifecycle for a single Woobe Instance with exactly one admin."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        token_codec: AccessTokenCodec,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._token_codec = token_codec
        self._sessions = SessionLifecycle(ttl_days=settings.refresh_token_ttl_days)

    async def status(self) -> dict[str, object]:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT instance_id, admin_user_id, initialized_at,
                               signup_mode, telemetry_enabled
                        FROM identity.instance_settings
                        WHERE id = 1
                        """
                    )
                )
            ).mappings().one_or_none()
        initialized = bool(
            row is not None
            and row["instance_id"] is not None
            and row["admin_user_id"] is not None
            and row["initialized_at"] is not None
        )
        return {
            "initialized": initialized,
            "instance_id": str(row["instance_id"]) if initialized else None,
            "signup_mode": str(row["signup_mode"]) if row is not None else "bootstrap",
            "telemetry_enabled": bool(row["telemetry_enabled"]) if row is not None else False,
        }

    async def ensure_registration_allowed(self, email: str) -> None:
        normalized_email = email.strip().lower()
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT admin_user_id, initialized_at, signup_mode
                        FROM identity.instance_settings
                        WHERE id = 1
                        """
                    )
                )
            ).mappings().one_or_none()
            if row is None or row["admin_user_id"] is None or row["initialized_at"] is None:
                raise ConflictError("Woobe Instance is not initialized. Bootstrap the Instance first.")
            signup_mode = str(row["signup_mode"])
            if signup_mode == "open":
                return
            if signup_mode == "disabled":
                raise AuthorizationError("Registration is disabled for this Woobe Instance")
            pending_invite = (
                await session.execute(
                    text(
                        """
                        SELECT 1 FROM identity.user_invites
                        WHERE lower(email) = :email
                          AND status = 'pending'
                          AND expires_at > now()
                        LIMIT 1
                        """
                    ),
                    {"email": normalized_email},
                )
            ).scalar_one_or_none()
            if pending_invite is None:
                raise AuthorizationError(
                    "Public registration is disabled. An active Workspace invite is required."
                )

    async def bootstrap(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> IssuedAuthentication:
        normalized_email = email.strip().lower()
        now = datetime.now(UTC)
        instance_id = uuid6.uuid7()
        async with IdentityUnitOfWork(self._session_factory) as uow:
            claim = await uow.session.execute(
                text(
                    """
                    INSERT INTO identity.instance_settings
                        (id, instance_id, admin_user_id, initialized_at,
                         signup_mode, telemetry_enabled, created_at, updated_at)
                    VALUES
                        (1, :instance_id, NULL, NULL, 'invite_only', false, :now, :now)
                    ON CONFLICT (id) DO NOTHING
                    RETURNING id
                    """
                ),
                {"instance_id": instance_id, "now": now},
            )
            if claim.scalar_one_or_none() is None:
                raise ConflictError("Woobe Instance is already initialized or being initialized")
            user_count = int(
                (await uow.session.execute(text("SELECT count(*) FROM identity.users"))).scalar_one()
                or 0
            )
            if user_count > 0:
                raise ConflictError("Woobe Instance bootstrap requires an empty pre-release database")
            if await uow.users.get_by_email(normalized_email):
                raise EmailAlreadyExistsError(normalized_email)

            user = await uow.users.save(
                User(email=normalized_email, password=hash_password(password))
            )
            await uow.outbox.write(
                aggregate_type="user",
                aggregate_id=user.id,
                event_type="user.created.v1",
                payload={"email": user.email, "instance_admin": True},
                routing_key="user.created.v1",
                idempotency_key=f"identity:user.created.v1:{user.id}",
            )
            session = await self._sessions.issue(
                uow,
                user_id=user.id,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            await uow.session.execute(
                text(
                    """
                    UPDATE identity.instance_settings
                    SET admin_user_id = :admin_user_id,
                        initialized_at = :now,
                        updated_at = :now
                    WHERE id = 1 AND admin_user_id IS NULL
                    """
                ),
                {"admin_user_id": user.id, "now": now},
            )
            return IssuedAuthentication(
                access_token=self._token_codec.issue(user_id=user.id, session_id=session.id),
                refresh_token=session.secret,
                session_id=session.id,
                token_type="Bearer",
                expires_in=self._token_codec.ttl_seconds,
                user=AuthenticatedUser(id=user.id, email=user.email, status=user.status.value),
            )
