from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.application.auth_types import (
    AuthenticatedUser,
    IssuedAuthentication,
)
from modules.identity.application.session_lifecycle import SessionLifecycle
from modules.identity.domain.entities import Organization, OrganizationMember, User
from modules.identity.domain.enums import MemberRole, MemberStatus, UserStatus
from modules.identity.domain.errors import EmailAlreadyExistsError, InvalidCredentialsError
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from shared.infra.config import Settings
from shared.infra.crypto import hash_password, verify_password
from shared.infra.errors import AuthenticationError
from shared.security.access_tokens import AccessTokenCodec


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
        organization_name: str,
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

            slug_base = re.sub(
                r"[^a-z0-9]+",
                "-",
                organization_name.lower(),
            ).strip("-")
            organization = await uow.organizations.save(
                Organization(
                    name=organization_name.strip(),
                    slug=f"{slug_base or 'organization'}-{str(user.id)[:8]}",
                )
            )
            member = await uow.members.save(
                OrganizationMember(
                    user_id=user.id,
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
            return self._authentication_result(user, session.id, session.secret)

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

    def _authentication_result(
        self,
        user: User,
        session_id: UUID,
        refresh_secret: str,
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
        )
