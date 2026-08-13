from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import uuid6
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.application.auth_types import AuthenticatedUser, IssuedAuthentication
from modules.identity.application.session_lifecycle import SessionLifecycle
from modules.identity.domain.entities import User, UserInvite
from modules.identity.domain.enums import InviteStatus, UserStatus
from modules.identity.domain.errors import EmailAlreadyExistsError, InvalidCredentialsError
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from shared.infra.config import Settings
from shared.infra.crypto import hash_password, verify_password
from shared.infra.errors import AuthenticationError, ConflictError, NotFoundError
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

    async def logout(self, *, session_id: UUID | None, secret: str | None) -> None:
        async with IdentityUnitOfWork(self._session_factory) as uow:
            await self._sessions.revoke(uow, session_id=session_id, secret=secret)

    async def get_user(self, user_id: UUID) -> AuthenticatedUser:
        async with IdentityUnitOfWork(self._session_factory) as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None or user.status != UserStatus.active:
                raise AuthenticationError("Authentication required")
            return AuthenticatedUser(id=user.id, email=user.email, status=user.status.value)

    async def create_invite(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        email: str,
        project_ids: list[UUID],
    ) -> UserInvite:
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise ConflictError("Invite email is required")
        unique_project_ids = list(dict.fromkeys(project_ids))
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=7)

        async with IdentityUnitOfWork(self._session_factory) as uow:
            await self._require_instance_admin(uow.session, actor_user_id)
            workspace = await uow.session.execute(
                text("SELECT 1 FROM core.workspaces WHERE id = :workspace_id AND status = 'active'"),
                {"workspace_id": workspace_id},
            )
            if workspace.scalar_one_or_none() is None:
                raise NotFoundError("Workspace not found")

            if unique_project_ids:
                query = text(
                    """
                    SELECT id FROM core.projects
                    WHERE workspace_id = :workspace_id AND id IN :project_ids
                    """
                ).bindparams(bindparam("project_ids", expanding=True))
                rows = await uow.session.execute(
                    query,
                    {"workspace_id": workspace_id, "project_ids": unique_project_ids},
                )
                valid_ids = {UUID(str(row[0])) for row in rows.all()}
                if valid_ids != set(unique_project_ids):
                    raise ConflictError("All invited Projects must belong to the Workspace")

            existing_user = await uow.users.get_by_email(normalized_email)
            if existing_user is not None:
                if await self._is_instance_admin(uow.session, existing_user.id):
                    raise ConflictError("The Instance admin cannot be invited to a Workspace")
                membership = await uow.session.execute(
                    text(
                        """
                        SELECT workspace_id FROM core.workspace_members
                        WHERE user_id = :user_id AND status = 'active'
                        LIMIT 1
                        """
                    ),
                    {"user_id": existing_user.id},
                )
                member_workspace = membership.scalar_one_or_none()
                if member_workspace is not None and UUID(str(member_workspace)) != workspace_id:
                    raise ConflictError("User already belongs to another Workspace")

            pending_other = await uow.session.execute(
                text(
                    """
                    SELECT id FROM identity.user_invites
                    WHERE lower(email) = :email
                      AND status = 'pending'
                      AND expires_at > now()
                      AND workspace_id <> :workspace_id
                    LIMIT 1
                    """
                ),
                {"email": normalized_email, "workspace_id": workspace_id},
            )
            if pending_other.scalar_one_or_none() is not None:
                raise ConflictError("A pending invite for another Workspace already exists")

            existing = await uow.session.execute(
                text(
                    """
                    SELECT id, status, created_at
                    FROM identity.user_invites
                    WHERE workspace_id = :workspace_id AND lower(email) = :email
                    FOR UPDATE
                    """
                ),
                {"workspace_id": workspace_id, "email": normalized_email},
            )
            row = existing.mappings().first()
            if row is not None and str(row["status"]) == InviteStatus.pending.value:
                raise ConflictError("A pending invite already exists for this email")

            if row is None:
                invite = await uow.invites.save(
                    UserInvite(
                        workspace_id=workspace_id,
                        email=normalized_email,
                        invited_by_user_id=actor_user_id,
                        expires_at=expires_at,
                    )
                )
            else:
                invite_id = UUID(str(row["id"]))
                await uow.session.execute(
                    text(
                        """
                        UPDATE identity.user_invites
                        SET status = 'pending', invited_by_user_id = :actor_user_id,
                            expires_at = :expires_at, accepted_at = NULL, updated_at = :now
                        WHERE id = :invite_id
                        """
                    ),
                    {
                        "invite_id": invite_id,
                        "actor_user_id": actor_user_id,
                        "expires_at": expires_at,
                        "now": now,
                    },
                )
                invite = UserInvite(
                    id=invite_id,
                    workspace_id=workspace_id,
                    email=normalized_email,
                    invited_by_user_id=actor_user_id,
                    status=InviteStatus.pending,
                    expires_at=expires_at,
                    created_at=row["created_at"],
                    updated_at=now,
                )

            await uow.session.execute(
                text(
                    """
                    UPDATE core.project_invite_access
                    SET status = 'cancelled', updated_at = :now
                    WHERE user_invite_id = :invite_id AND status = 'pending'
                    """
                ),
                {"invite_id": invite.id, "now": now},
            )
            for project_id in unique_project_ids:
                await uow.session.execute(
                    text(
                        """
                        INSERT INTO core.project_invite_access
                            (id, project_id, user_invite_id, status, granted_by_user_id,
                             created_at, updated_at)
                        VALUES
                            (:id, :project_id, :invite_id, 'pending', :actor_user_id,
                             :now, :now)
                        ON CONFLICT (project_id, user_invite_id)
                        DO UPDATE SET status = 'pending',
                                      granted_by_user_id = EXCLUDED.granted_by_user_id,
                                      updated_at = EXCLUDED.updated_at
                        """
                    ),
                    {
                        "id": uuid6.uuid7(),
                        "project_id": project_id,
                        "invite_id": invite.id,
                        "actor_user_id": actor_user_id,
                        "now": now,
                    },
                )
            await uow.outbox.write(
                aggregate_type="user_invite",
                aggregate_id=invite.id,
                event_type="user.invite_created.v1",
                payload={
                    "workspace_id": str(workspace_id),
                    "email": normalized_email,
                    "project_ids": [str(project_id) for project_id in unique_project_ids],
                },
                routing_key="user.invite_created.v1",
                idempotency_key=f"identity:user.invite_created.v1:{invite.id}:{int(now.timestamp())}",
            )
            return invite

    async def list_pending_invites(self, user_id: UUID) -> list[dict[str, object]]:
        async with IdentityUnitOfWork(self._session_factory) as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None or user.status != UserStatus.active:
                raise AuthenticationError("Authentication required")
            result = await uow.session.execute(
                text(
                    """
                    SELECT i.id, i.workspace_id, i.email, i.status, i.expires_at,
                           i.created_at, w.name AS workspace_name, w.slug AS workspace_slug,
                           COUNT(pia.id) FILTER (WHERE pia.status = 'pending') AS project_count
                    FROM identity.user_invites i
                    JOIN core.workspaces w ON w.id = i.workspace_id
                    LEFT JOIN core.project_invite_access pia
                      ON pia.user_invite_id = i.id AND pia.status = 'pending'
                    WHERE lower(i.email) = :email
                      AND i.status = 'pending'
                      AND i.expires_at > now()
                      AND w.status = 'active'
                    GROUP BY i.id, w.id
                    ORDER BY i.created_at DESC
                    """
                ),
                {"email": user.email.strip().lower()},
            )
            return [dict(row) for row in result.mappings().all()]

    async def list_invites(
        self, *, actor_user_id: UUID, workspace_id: UUID
    ) -> list[dict[str, object]]:
        async with IdentityUnitOfWork(self._session_factory) as uow:
            await self._require_instance_admin(uow.session, actor_user_id)
            result = await uow.session.execute(
                text(
                    """
                    SELECT i.id, i.workspace_id, i.email, i.status, i.expires_at,
                           i.created_at,
                           COUNT(pia.id) FILTER (WHERE pia.status = 'pending') AS project_count
                    FROM identity.user_invites i
                    LEFT JOIN core.project_invite_access pia ON pia.user_invite_id = i.id
                    WHERE i.workspace_id = :workspace_id
                    GROUP BY i.id
                    ORDER BY i.created_at DESC
                    """
                ),
                {"workspace_id": workspace_id},
            )
            return [dict(row) for row in result.mappings().all()]

    async def cancel_invite(self, *, actor_user_id: UUID, invite_id: UUID) -> None:
        async with IdentityUnitOfWork(self._session_factory) as uow:
            await self._require_instance_admin(uow.session, actor_user_id)
            now = datetime.now(UTC)
            result = await uow.session.execute(
                text(
                    """
                    UPDATE identity.user_invites
                    SET status = 'cancelled', updated_at = :now
                    WHERE id = :invite_id AND status = 'pending'
                    RETURNING id
                    """
                ),
                {"invite_id": invite_id, "now": now},
            )
            if result.scalar_one_or_none() is None:
                raise NotFoundError("Pending invite not found")
            await uow.session.execute(
                text(
                    """
                    UPDATE core.project_invite_access
                    SET status = 'cancelled', updated_at = :now
                    WHERE user_invite_id = :invite_id AND status = 'pending'
                    """
                ),
                {"invite_id": invite_id, "now": now},
            )

    async def accept_invite(self, *, user_id: UUID, invite_id: UUID) -> dict[str, object]:
        async with IdentityUnitOfWork(self._session_factory) as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None or user.status != UserStatus.active:
                raise AuthenticationError("Authentication required")
            if await self._is_instance_admin(uow.session, user_id):
                raise ConflictError("The Instance admin cannot join a Workspace")

            result = await uow.session.execute(
                text(
                    """
                    SELECT id, workspace_id, email, status, expires_at
                    FROM identity.user_invites
                    WHERE id = :invite_id
                    FOR UPDATE
                    """
                ),
                {"invite_id": invite_id},
            )
            invite = result.mappings().first()
            if invite is None or str(invite["email"]).strip().lower() != user.email.strip().lower():
                raise NotFoundError("Invite not found")
            if str(invite["status"]) != InviteStatus.pending.value:
                raise ConflictError("Invite is no longer pending")
            if invite["expires_at"] is not None and invite["expires_at"] <= datetime.now(UTC):
                await uow.session.execute(
                    text("UPDATE identity.user_invites SET status = 'expired', updated_at = :now WHERE id = :invite_id"),
                    {"invite_id": invite_id, "now": datetime.now(UTC)},
                )
                raise ConflictError("Invite has expired")

            workspace_id = UUID(str(invite["workspace_id"]))
            membership = await uow.session.execute(
                text(
                    """
                    SELECT id, workspace_id, status
                    FROM core.workspace_members
                    WHERE user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT 1
                    FOR UPDATE
                    """
                ),
                {"user_id": user_id},
            )
            current = membership.mappings().first()
            now = datetime.now(UTC)
            if current is not None and str(current["status"]) == "active":
                if UUID(str(current["workspace_id"])) != workspace_id:
                    raise ConflictError("User already belongs to another Workspace")
                member_id = UUID(str(current["id"]))
            elif current is None:
                member_id = uuid6.uuid7()
                await uow.session.execute(
                    text(
                        """
                        INSERT INTO core.workspace_members
                            (id, workspace_id, user_id, status, joined_at, created_at, updated_at)
                        VALUES
                            (:id, :workspace_id, :user_id, 'active', :now, :now, :now)
                        """
                    ),
                    {"id": member_id, "workspace_id": workspace_id, "user_id": user_id, "now": now},
                )
            else:
                member_id = UUID(str(current["id"]))
                await uow.session.execute(
                    text(
                        """
                        UPDATE core.workspace_members
                        SET workspace_id = :workspace_id, status = 'active', joined_at = :now, updated_at = :now
                        WHERE id = :id
                        """
                    ),
                    {"id": member_id, "workspace_id": workspace_id, "now": now},
                )

            await uow.session.execute(
                text(
                    """
                    INSERT INTO core.project_members
                        (id, project_id, user_id, status, granted_by_user_id, created_at, updated_at)
                    SELECT gen_random_uuid(), pia.project_id, :user_id, 'active',
                           pia.granted_by_user_id, :now, :now
                    FROM core.project_invite_access pia
                    JOIN core.projects p ON p.id = pia.project_id
                    WHERE pia.user_invite_id = :invite_id
                      AND pia.status = 'pending'
                      AND p.workspace_id = :workspace_id
                    ON CONFLICT (project_id, user_id)
                    DO UPDATE SET status = 'active',
                                  granted_by_user_id = EXCLUDED.granted_by_user_id,
                                  updated_at = EXCLUDED.updated_at
                    """
                ),
                {
                    "user_id": user_id,
                    "invite_id": invite_id,
                    "workspace_id": workspace_id,
                    "now": now,
                },
            )
            await uow.session.execute(
                text("UPDATE core.project_invite_access SET status = 'applied', updated_at = :now WHERE user_invite_id = :invite_id AND status = 'pending'"),
                {"invite_id": invite_id, "now": now},
            )
            await uow.session.execute(
                text("UPDATE identity.user_invites SET status = 'accepted', accepted_at = :now, updated_at = :now WHERE id = :invite_id"),
                {"invite_id": invite_id, "now": now},
            )
            await uow.outbox.write(
                aggregate_type="user_invite",
                aggregate_id=invite_id,
                event_type="user.invite_accepted.v1",
                payload={"user_id": str(user_id), "workspace_id": str(workspace_id)},
                routing_key="user.invite_accepted.v1",
                idempotency_key=f"identity:user.invite_accepted.v1:{invite_id}",
            )
            workspace = await uow.session.execute(
                text("SELECT id, name, slug, status, created_at, updated_at FROM core.workspaces WHERE id = :workspace_id"),
                {"workspace_id": workspace_id},
            )
            row = workspace.mappings().first()
            if row is None:
                raise NotFoundError("Workspace not found")
            return dict(row)

    @staticmethod
    async def _is_instance_admin(session: AsyncSession, user_id: UUID) -> bool:
        result = await session.execute(
            text("SELECT 1 FROM identity.instance_settings WHERE id = 1 AND admin_user_id = :user_id AND initialized_at IS NOT NULL"),
            {"user_id": user_id},
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def _require_instance_admin(cls, session: AsyncSession, user_id: UUID) -> None:
        if not await cls._is_instance_admin(session, user_id):
            from shared.infra.errors import AuthorizationError
            raise AuthorizationError("Instance admin access is required")

    def _authentication_result(
        self, user: User, session_id: UUID, refresh_secret: str
    ) -> IssuedAuthentication:
        return IssuedAuthentication(
            access_token=self._token_codec.issue(user_id=user.id, session_id=session_id),
            refresh_token=refresh_secret,
            session_id=session_id,
            token_type="Bearer",
            expires_in=self._token_codec.ttl_seconds,
            user=AuthenticatedUser(id=user.id, email=user.email, status=user.status.value),
        )
