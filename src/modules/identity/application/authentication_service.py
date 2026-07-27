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
from modules.identity.application.session_lifecycle import SessionLifecycle
from modules.identity.domain.entities import Organization, OrganizationMember, User
from modules.identity.domain.enums import InviteStatus, MemberRole, MemberStatus, UserStatus
from modules.identity.domain.errors import EmailAlreadyExistsError, InvalidCredentialsError
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from shared.infra.config import Settings
from shared.infra.crypto import hash_password, verify_password
from shared.infra.errors import AuthenticationError, ConflictError, NotFoundError
from shared.security.access_tokens import AccessTokenCodec


DEFAULT_ORGANIZATION_NAME = "My Organization"


class AuthenticationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        token_codec: AccessTokenCodec,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._token_codec = token_codec
        self._sessions = SessionLifecycle(ttl_days=settings.refresh_token_ttl_days)

    async def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> IssuedAuthentication:
        async with IdentityUnitOfWork(self._session_factory) as uow:
            user = await uow.users.get_by_email(email.strip().lower())
            if (
                user is None
                or user.status != UserStatus.active
                or not verify_password(password, user.password)
            ):
                raise InvalidCredentialsError("Invalid credentials")
            session = await self._sessions.issue(
                uow,
                user_id=user.id,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            return self._authentication_result(user, session.id, session.secret)

    async def register(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> IssuedAuthentication:
        normalized_email = email.strip().lower()
        async with IdentityUnitOfWork(self._session_factory) as uow:
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

            organization = await self._create_owned_organization(
                uow,
                user_id=user.id,
                name=DEFAULT_ORGANIZATION_NAME,
                slug=f"org-{str(user.id)[:8]}",
            )

            session = await self._sessions.issue(
                uow,
                user_id=user.id,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            return self._authentication_result(
                user,
                session.id,
                session.secret,
                organization=organization,
            )

    async def create_organization(
        self,
        *,
        user_id: UUID,
        name: str,
        slug: str,
    ) -> Organization:
        async with IdentityUnitOfWork(self._session_factory) as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None or user.status != UserStatus.active:
                raise AuthenticationError("Authentication required")
            return await self._create_owned_organization(
                uow,
                user_id=user.id,
                name=name.strip(),
                slug=slug.strip().lower(),
            )

    async def refresh(
        self,
        *,
        session_id: UUID,
        secret: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> IssuedAuthentication:
        async with IdentityUnitOfWork(self._session_factory) as uow:
            session = await self._sessions.rotate(
                uow,
                session_id=session_id,
                secret=secret,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            user = await uow.users.get_by_id(session.user_id)
            if user is None or user.status != UserStatus.active:
                await self._sessions.revoke_all(uow, session.user_id)
                raise AuthenticationError("Invalid refresh session")
            return self._authentication_result(user, session.id, session.secret)

    async def logout(
        self,
        *,
        session_id: UUID | None,
        secret: str | None,
    ) -> None:
        async with IdentityUnitOfWork(self._session_factory) as uow:
            await self._sessions.revoke(
                uow,
                session_id=session_id,
                secret=secret,
            )

    async def get_user(self, user_id: UUID) -> AuthenticatedUser:
        async with IdentityUnitOfWork(self._session_factory) as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None or user.status != UserStatus.active:
                raise AuthenticationError("Authentication required")
            return AuthenticatedUser(
                id=user.id,
                email=user.email,
                status=user.status.value,
            )

    async def list_organizations(self, user_id: UUID) -> list[Organization]:
        async with IdentityUnitOfWork(self._session_factory) as uow:
            memberships = await uow.members.list_by_user(user_id)
            organizations: list[Organization] = []
            for membership in memberships:
                if membership.status != MemberStatus.active:
                    continue
                organization = await uow.organizations.get_by_id(
                    membership.organization_id
                )
                if organization is not None:
                    organizations.append(organization)
            return organizations

    async def list_pending_invites(self, user_id: UUID) -> list[dict[str, object]]:
        async with IdentityUnitOfWork(self._session_factory) as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None or user.status != UserStatus.active:
                raise AuthenticationError("Authentication required")
            result = await uow.session.execute(
                text(
                    """
                    SELECT i.id, i.organization_id, i.email, i.role, i.status,
                           i.expires_at, i.created_at,
                           o.name AS organization_name, o.slug AS organization_slug
                    FROM identity.organization_invites AS i
                    JOIN identity.organizations AS o ON o.id = i.organization_id
                    WHERE lower(i.email) = :email
                      AND i.status = 'pending'
                      AND i.expires_at > now()
                      AND o.status = 'active'
                    ORDER BY i.created_at DESC
                    """
                ),
                {"email": user.email.strip().lower()},
            )
            return [dict(row) for row in result.mappings().all()]

    async def accept_invite(self, *, user_id: UUID, invite_id: UUID) -> Organization:
        async with IdentityUnitOfWork(self._session_factory) as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None or user.status != UserStatus.active:
                raise AuthenticationError("Authentication required")

            result = await uow.session.execute(
                text(
                    """
                    SELECT id, organization_id, email, role, status, expires_at
                    FROM identity.organization_invites
                    WHERE id = :invite_id
                    FOR UPDATE
                    """
                ),
                {"invite_id": invite_id},
            )
            invite = result.mappings().first()
            if invite is None:
                raise NotFoundError("Invite not found")
            if str(invite["status"]) != InviteStatus.pending.value:
                raise ConflictError("Invite is no longer pending")
            if str(invite["email"]).strip().lower() != user.email.strip().lower():
                raise NotFoundError("Invite not found")
            expires_at = invite["expires_at"]
            if expires_at is not None and expires_at <= datetime.now(UTC):
                await uow.session.execute(
                    text(
                        """
                        UPDATE identity.organization_invites
                        SET status = 'expired', updated_at = :now
                        WHERE id = :invite_id
                        """
                    ),
                    {"invite_id": invite_id, "now": datetime.now(UTC)},
                )
                raise ConflictError("Invite has expired")

            organization_id = UUID(str(invite["organization_id"]))
            role = MemberRole(str(invite["role"]))
            existing = await uow.members.get_by_organization_and_user(
                organization_id,
                user.id,
            )
            joined_at = datetime.now(UTC)
            member_id: UUID
            membership_changed = False
            if existing is None:
                member = await uow.members.save(
                    OrganizationMember(
                        user_id=user.id,
                        organization_id=organization_id,
                        role=role,
                        joined_at=joined_at,
                    )
                )
                member_id = member.id
                membership_changed = True
            else:
                member_id = existing.id
                if existing.status != MemberStatus.active or existing.role != role:
                    await uow.session.execute(
                        text(
                            """
                            UPDATE identity.organization_members
                            SET role = :role, status = 'active', joined_at = :joined_at,
                                updated_at = :joined_at
                            WHERE id = :member_id
                            """
                        ),
                        {
                            "member_id": existing.id,
                            "role": role.value,
                            "joined_at": joined_at,
                        },
                    )
                    membership_changed = True

            now = datetime.now(UTC)
            await uow.session.execute(
                text(
                    """
                    UPDATE identity.organization_invites
                    SET status = 'accepted', accepted_at = :now, updated_at = :now
                    WHERE id = :invite_id
                    """
                ),
                {"invite_id": invite_id, "now": now},
            )

            if membership_changed:
                await uow.outbox.write(
                    aggregate_type="organization_member",
                    aggregate_id=member_id,
                    event_type="organization.member_added.v1",
                    payload={
                        "user_id": str(user.id),
                        "organization_id": str(organization_id),
                        "role": role.value,
                    },
                    routing_key="organization.member_added.v1",
                    idempotency_key=f"identity:organization.member_added.v1:{member_id}",
                )

            organization = await uow.organizations.get_by_id(organization_id)
            if organization is None:
                raise NotFoundError("Organization not found")
            return organization

    async def _create_owned_organization(
        self,
        uow: IdentityUnitOfWork,
        *,
        user_id: UUID,
        name: str,
        slug: str,
    ) -> Organization:
        if await uow.organizations.get_by_slug(slug):
            raise ConflictError(f"Organization with slug '{slug}' already exists")

        organization = await uow.organizations.save(
            Organization(name=name, slug=slug)
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
                user_id=user_id,
                organization_id=organization.id,
                role=MemberRole.owner,
                joined_at=datetime.now(UTC),
            )
        )
        await uow.outbox.write(
            aggregate_type="organization_member",
            aggregate_id=member.id,
            event_type="organization.member_added.v1",
            payload={
                "user_id": str(user_id),
                "organization_id": str(organization.id),
                "role": member.role.value,
            },
            routing_key="organization.member_added.v1",
            idempotency_key=f"identity:organization.member_added.v1:{member.id}",
        )
        return organization

    def _authentication_result(
        self,
        user: User,
        session_id: UUID,
        refresh_secret: str,
        *,
        organization: Organization | None = None,
    ) -> IssuedAuthentication:
        return IssuedAuthentication(
            access_token=self._token_codec.issue(
                user_id=user.id,
                session_id=session_id,
            ),
            refresh_token=refresh_secret,
            session_id=session_id,
            token_type="Bearer",
            expires_in=self._token_codec.ttl_seconds,
            user=AuthenticatedUser(
                id=user.id,
                email=user.email,
                status=user.status.value,
            ),
            organization=(
                AuthenticatedOrganization(
                    id=organization.id,
                    name=organization.name,
                    slug=organization.slug,
                    status=organization.status.value,
                )
                if organization is not None
                else None
            ),
        )
