from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.application.auth_types import (
    AuthenticatedOrganization,
    AuthenticatedUser,
    IssuedAuthentication,
)
from modules.identity.application.authentication_service import DEFAULT_ORGANIZATION_NAME
from modules.identity.application.session_lifecycle import SessionLifecycle
from modules.identity.domain.entities import Organization, OrganizationMember, User
from modules.identity.domain.enums import MemberRole
from modules.identity.domain.errors import EmailAlreadyExistsError
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from shared.infra.config import Settings
from shared.infra.crypto import hash_password
from shared.infra.errors import AuthorizationError, ConflictError, NotFoundError
from shared.security.access_tokens import AccessTokenCodec


class InstanceService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        token_codec: AccessTokenCodec,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._token_codec = token_codec
        self._settings = settings
        self._sessions = SessionLifecycle(ttl_days=settings.refresh_token_ttl_days)

    async def status(self) -> dict[str, object]:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT owner_user_id, initialized_at, signup_mode, telemetry_enabled
                        FROM identity.instance_settings
                        WHERE id = 1
                        """
                    )
                )
            ).mappings().one_or_none()
            user_count = int(
                (
                    await session.execute(
                        text("SELECT count(*) FROM identity.users")
                    )
                ).scalar_one()
                or 0
            )

        initialized = bool(
            row is not None
            and row["owner_user_id"] is not None
            and row["initialized_at"] is not None
        )
        return {
            "initialized": initialized,
            "edition": self._settings.edition,
            "signup_mode": (
                str(row["signup_mode"])
                if row is not None
                else "open"
                if self._settings.is_cloud
                else "bootstrap"
            ),
            "telemetry_enabled": bool(row["telemetry_enabled"]) if row is not None else False,
            "requires_existing_owner_bootstrap": (
                self._settings.edition == "community" and not initialized and user_count > 0
            ),
        }

    async def ensure_registration_allowed(self, email: str) -> None:
        if self._settings.is_cloud:
            return

        normalized_email = email.strip().lower()
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT owner_user_id, initialized_at, signup_mode
                        FROM identity.instance_settings
                        WHERE id = 1
                        """
                    )
                )
            ).mappings().one_or_none()
            if (
                row is None
                or row["owner_user_id"] is None
                or row["initialized_at"] is None
            ):
                raise ConflictError(
                    "Woobe Community is not initialized. Bootstrap the instance before registration."
                )

            signup_mode = str(row["signup_mode"])
            if signup_mode == "open":
                return
            if signup_mode == "disabled":
                raise AuthorizationError("Registration is disabled for this Woobe instance")

            pending_invite = (
                await session.execute(
                    text(
                        """
                        SELECT 1
                        FROM identity.organization_invites
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
                    "Public registration is disabled. An active Organization invite is required."
                )

    async def bootstrap(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> IssuedAuthentication:
        if self._settings.edition != "community":
            raise ConflictError("Instance bootstrap is only available in Woobe Community")

        normalized_email = email.strip().lower()
        now = datetime.now(UTC)
        async with IdentityUnitOfWork(self._session_factory) as uow:
            claim = await uow.session.execute(
                text(
                    """
                    INSERT INTO identity.instance_settings
                        (id, owner_user_id, initialized_at, signup_mode,
                         telemetry_enabled, created_at, updated_at)
                    VALUES
                        (1, NULL, NULL, 'invite_only', false, :now, :now)
                    ON CONFLICT (id) DO NOTHING
                    RETURNING id
                    """
                ),
                {"now": now},
            )
            if claim.scalar_one_or_none() is None:
                raise ConflictError("Woobe instance is already initialized or being initialized")

            user_count = int(
                (
                    await uow.session.execute(text("SELECT count(*) FROM identity.users"))
                ).scalar_one()
                or 0
            )
            if user_count > 0:
                raise ConflictError(
                    "Existing Woobe installation detected. Run the explicit existing-owner bootstrap command."
                )
            if await uow.users.get_by_email(normalized_email):
                raise EmailAlreadyExistsError(normalized_email)

            user = await uow.users.save(
                User(email=normalized_email, password=hash_password(password))
            )
            await uow.outbox.write(
                aggregate_type="user",
                aggregate_id=user.id,
                event_type="user.created.v1",
                payload={"email": user.email},
                routing_key="user.created.v1",
                idempotency_key=f"identity:user.created.v1:{user.id}",
            )

            organization = await uow.organizations.save(
                Organization(
                    name=DEFAULT_ORGANIZATION_NAME,
                    slug=f"org-{str(user.id)[:8]}",
                )
            )
            await uow.outbox.write(
                aggregate_type="organization",
                aggregate_id=organization.id,
                event_type="organization.created.v1",
                payload={"name": organization.name, "slug": organization.slug},
                routing_key="organization.created.v1",
                idempotency_key=f"identity:organization.created.v1:{organization.id}",
            )

            member = await uow.members.save(
                OrganizationMember(
                    user_id=user.id,
                    organization_id=organization.id,
                    role=MemberRole.owner,
                    joined_at=now,
                )
            )
            await uow.outbox.write(
                aggregate_type="organization_member",
                aggregate_id=member.id,
                event_type="organization.member_added.v1",
                payload={
                    "user_id": str(user.id),
                    "organization_id": str(organization.id),
                    "role": member.role.value,
                },
                routing_key="organization.member_added.v1",
                idempotency_key=f"identity:organization.member_added.v1:{member.id}",
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
                    SET owner_user_id = :owner_user_id,
                        initialized_at = :initialized_at,
                        updated_at = :initialized_at
                    WHERE id = 1
                    """
                ),
                {"owner_user_id": user.id, "initialized_at": now},
            )

            return IssuedAuthentication(
                access_token=self._token_codec.issue(
                    user_id=user.id,
                    session_id=session.id,
                ),
                refresh_token=session.secret,
                session_id=session.id,
                token_type="Bearer",
                expires_in=self._token_codec.ttl_seconds,
                user=AuthenticatedUser(
                    id=user.id,
                    email=user.email,
                    status=user.status.value,
                ),
                organization=AuthenticatedOrganization(
                    id=organization.id,
                    name=organization.name,
                    slug=organization.slug,
                    status=organization.status.value,
                ),
            )

    async def bootstrap_existing_owner(self, *, owner_email: str) -> UUID:
        if self._settings.edition != "community":
            raise ConflictError("Existing-owner bootstrap is only available in Woobe Community")

        normalized_email = owner_email.strip().lower()
        now = datetime.now(UTC)
        async with IdentityUnitOfWork(self._session_factory) as uow:
            owner = (
                await uow.session.execute(
                    text(
                        """
                        SELECT u.id
                        FROM identity.users AS u
                        JOIN identity.organization_members AS member
                          ON member.user_id = u.id
                        WHERE lower(u.email) = :email
                          AND u.status = 'active'
                          AND member.status = 'active'
                          AND member.role = 'owner'
                        LIMIT 1
                        """
                    ),
                    {"email": normalized_email},
                )
            ).scalar_one_or_none()
            if owner is None:
                raise NotFoundError(
                    "No active Organization owner exists with the supplied email"
                )

            inserted = await uow.session.execute(
                text(
                    """
                    INSERT INTO identity.instance_settings
                        (id, owner_user_id, initialized_at, signup_mode,
                         telemetry_enabled, created_at, updated_at)
                    VALUES
                        (1, :owner_user_id, :now, 'invite_only', false, :now, :now)
                    ON CONFLICT (id) DO NOTHING
                    RETURNING owner_user_id
                    """
                ),
                {"owner_user_id": owner, "now": now},
            )
            initialized_owner = inserted.scalar_one_or_none()
            if initialized_owner is None:
                raise ConflictError("Woobe instance is already initialized")
            return UUID(str(initialized_owner))
