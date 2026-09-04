from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncEngine

from modules.identity.application.auth_types import (
    AuthenticatedWorkspace,
    AuthenticatedUser,
    IssuedAuthentication,
)
from modules.identity.infra.services.session_lifecycle import SessionLifecycle
from modules.identity.domain.entities import (
    Workspace,
    WorkspaceInvite,
    WorkspaceMember,
    User,
)
from modules.identity.domain.enums import InviteStatus, MemberRole, MemberStatus, UserStatus
from modules.identity.domain.errors import EmailAlreadyExistsError, InvalidCredentialsError
from modules.identity.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUserRepository,
    SQLAlchemyWorkspaceInviteRepository,
    SQLAlchemyWorkspaceMemberRepository,
    SQLAlchemyWorkspaceRepository,
)
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from shared.infra.config import Settings
from shared.infra.crypto import hash_password, verify_password
from shared.infra.errors import AuthenticationError, ConflictError, NotFoundError
from shared.security.access_tokens import AccessTokenCodec


DEFAULT_WORKSPACE_NAME = "My Workspace"


class AuthenticationService:
    def __init__(
        self,
        engine: AsyncEngine,
        token_codec: AccessTokenCodec,
        settings: Settings,
    ) -> None:
        self._engine = engine
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
        async with IdentityUnitOfWork(self._engine) as uow:
            user = await SQLAlchemyUserRepository(uow).get_by_email(email.strip().lower())
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
        async with IdentityUnitOfWork(self._engine) as uow:
            if await SQLAlchemyUserRepository(uow).get_by_email(normalized_email):
                raise EmailAlreadyExistsError(normalized_email)

            user = await SQLAlchemyUserRepository(uow).save(
                User(email=normalized_email, password=hash_password(password))
            )
            await SQLAlchemyOutboxEventWriter(uow).write(
                aggregate_type="user",
                aggregate_id=user.id,
                event_type="user.created.v1",
                payload={"email": user.email},
                routing_key="user.created.v1",
                idempotency_key=f"identity:user.created.v1:{user.id}",
            )

            workspace = await self._create_owned_workspace(
                uow,
                user_id=user.id,
                name=DEFAULT_WORKSPACE_NAME,
                slug=f"workspace-{str(user.id)[:8]}",
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
                workspace=workspace,
            )

    async def create_workspace(
        self,
        *,
        user_id: UUID,
        name: str,
        slug: str,
    ) -> Workspace:
        async with IdentityUnitOfWork(self._engine) as uow:
            user = await SQLAlchemyUserRepository(uow).get_by_id(user_id)
            if user is None or user.status != UserStatus.active:
                raise AuthenticationError("Authentication required")
            return await self._create_owned_workspace(
                uow,
                user_id=user.id,
                name=name.strip(),
                slug=slug.strip().lower(),
            )

    async def create_invite(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        email: str,
        role: MemberRole,
        project_ids: list[UUID],
    ) -> WorkspaceInvite:
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise ConflictError("Invite email is required")

        unique_project_ids = list(dict.fromkeys(project_ids))
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=7)

        async with IdentityUnitOfWork(self._engine) as uow:
            workspace = await SQLAlchemyWorkspaceRepository(uow).get_by_id(workspace_id)
            if workspace is None:
                raise NotFoundError("Workspace not found")

            if unique_project_ids:
                project_query = text(
                    """
                    SELECT id
                    FROM core.projects
                    WHERE workspace_id = :workspace_id
                      AND id IN :project_ids
                    """
                ).bindparams(bindparam("project_ids", expanding=True))
                project_result = await uow.session.execute(
                    project_query,
                    {
                        "workspace_id": workspace_id,
                        "project_ids": unique_project_ids,
                    },
                )
                valid_project_ids = {UUID(str(row[0])) for row in project_result.all()}
                if valid_project_ids != set(unique_project_ids):
                    raise NotFoundError("One or more Projects do not belong to this Workspace")

            existing_result = await uow.session.execute(
                text(
                    """
                    SELECT id, status, created_at
                    FROM identity.workspace_invites
                    WHERE workspace_id = :workspace_id
                      AND lower(email) = :email
                    FOR UPDATE
                    """
                ),
                {"workspace_id": workspace_id, "email": normalized_email},
            )
            existing = existing_result.mappings().first()
            if existing is not None and str(existing["status"]) == InviteStatus.pending.value:
                raise ConflictError("A pending invite already exists for this email")

            if existing is None:
                invite = await SQLAlchemyWorkspaceInviteRepository(uow).save(
                    WorkspaceInvite(
                        workspace_id=workspace_id,
                        email=normalized_email,
                        role=role,
                        token_hash="",
                        invited_by_user_id=actor_user_id,
                        expires_at=expires_at,
                    )
                )
            else:
                invite_id = UUID(str(existing["id"]))
                await uow.session.execute(
                    text(
                        """
                        UPDATE identity.workspace_invites
                        SET role = :role,
                            status = 'pending',
                            invited_by_user_id = :actor_user_id,
                            expires_at = :expires_at,
                            accepted_at = NULL,
                            updated_at = :now
                        WHERE id = :invite_id
                        """
                    ),
                    {
                        "invite_id": invite_id,
                        "role": role.value,
                        "actor_user_id": actor_user_id,
                        "expires_at": expires_at,
                        "now": now,
                    },
                )
                invite = WorkspaceInvite(
                    id=invite_id,
                    workspace_id=workspace_id,
                    email=normalized_email,
                    role=role,
                    token_hash="",
                    invited_by_user_id=actor_user_id,
                    status=InviteStatus.pending,
                    expires_at=expires_at,
                    created_at=existing["created_at"],
                    updated_at=now,
                )

            await uow.session.execute(
                text(
                    """
                    UPDATE core.project_invite_access
                    SET status = 'cancelled', updated_at = :now
                    WHERE workspace_invite_id = :invite_id
                      AND status = 'pending'
                    """
                ),
                {"invite_id": invite.id, "now": now},
            )
            for project_id in unique_project_ids:
                await uow.session.execute(
                    text(
                        """
                        INSERT INTO core.project_invite_access
                            (id, project_id, workspace_invite_id, status,
                             granted_by_user_id, created_at, updated_at)
                        VALUES
                            (gen_random_uuid(), :project_id, :invite_id, 'pending',
                             :actor_user_id, :now, :now)
                        ON CONFLICT (project_id, workspace_invite_id)
                        DO UPDATE SET status = 'pending',
                                      granted_by_user_id = EXCLUDED.granted_by_user_id,
                                      updated_at = EXCLUDED.updated_at
                        """
                    ),
                    {
                        "project_id": project_id,
                        "invite_id": invite.id,
                        "actor_user_id": actor_user_id,
                        "now": now,
                    },
                )

            await SQLAlchemyOutboxEventWriter(uow).write(
                aggregate_type="workspace_invite",
                aggregate_id=invite.id,
                event_type="workspace.invite_created.v1",
                payload={
                    "workspace_id": str(workspace_id),
                    "email": normalized_email,
                    "role": role.value,
                    "project_ids": [str(project_id) for project_id in unique_project_ids],
                },
                routing_key="workspace.invite_created.v1",
                idempotency_key=(
                    f"identity:workspace.invite_created.v1:{invite.id}:{int(now.timestamp())}"
                ),
            )
            return invite

    async def refresh(
        self,
        *,
        session_id: UUID,
        secret: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> IssuedAuthentication:
        async with IdentityUnitOfWork(self._engine) as uow:
            session = await self._sessions.rotate(
                uow,
                session_id=session_id,
                secret=secret,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            user = await SQLAlchemyUserRepository(uow).get_by_id(session.user_id)
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
        async with IdentityUnitOfWork(self._engine) as uow:
            await self._sessions.revoke(
                uow,
                session_id=session_id,
                secret=secret,
            )

    async def get_user(self, user_id: UUID) -> AuthenticatedUser:
        async with IdentityUnitOfWork(self._engine) as uow:
            user = await SQLAlchemyUserRepository(uow).get_by_id(user_id)
            if user is None or user.status != UserStatus.active:
                raise AuthenticationError("Authentication required")
            return AuthenticatedUser(
                id=user.id,
                email=user.email,
                status=user.status.value,
            )

    async def list_workspaces(self, user_id: UUID) -> list[dict[str, object]]:
        async with IdentityUnitOfWork(self._engine) as uow:
            result = await uow.session.execute(
                text(
                    """
                    SELECT w.id, w.name, w.slug, w.status, w.created_at,
                           wm.role AS membership_role,
                           (wm.role IN ('owner', 'admin')) AS can_manage_workspace,
                           CASE
                               WHEN wm.role = 'owner' THEN 'implicit_owner'
                               ELSE 'assigned_projects'
                           END AS access_mode,
                           CASE
                               WHEN wm.role = 'owner' THEN (
                                   SELECT COUNT(*)
                                   FROM core.projects AS p
                                   WHERE p.workspace_id = w.id
                               )
                               ELSE (
                                   SELECT COUNT(*)
                                   FROM core.project_members AS pm
                                   JOIN core.projects AS p ON p.id = pm.project_id
                                   WHERE pm.user_id = :user_id
                                     AND pm.status = 'active'
                                     AND p.workspace_id = w.id
                               )
                           END AS accessible_project_count
                    FROM identity.workspace_members AS wm
                    JOIN identity.workspaces AS w ON w.id = wm.workspace_id
                    WHERE wm.user_id = :user_id
                      AND wm.status = 'active'
                      AND w.status = 'active'
                    ORDER BY w.created_at DESC
                    """
                ),
                {"user_id": user_id},
            )
            return [dict(row) for row in result.mappings().all()]

    async def list_pending_invites(self, user_id: UUID) -> list[dict[str, object]]:
        async with IdentityUnitOfWork(self._engine) as uow:
            user = await SQLAlchemyUserRepository(uow).get_by_id(user_id)
            if user is None or user.status != UserStatus.active:
                raise AuthenticationError("Authentication required")
            result = await uow.session.execute(
                text(
                    """
                    SELECT i.id, i.workspace_id, i.email, i.role, i.status,
                           i.expires_at, i.created_at,
                           w.name AS workspace_name, w.slug AS workspace_slug,
                           COUNT(pia.id) FILTER (WHERE pia.status = 'pending') AS project_count
                    FROM identity.workspace_invites AS i
                    JOIN identity.workspaces AS w ON w.id = i.workspace_id
                    LEFT JOIN core.project_invite_access AS pia
                      ON pia.workspace_invite_id = i.id
                     AND pia.status = 'pending'
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

    async def accept_invite(self, *, user_id: UUID, invite_id: UUID) -> Workspace:
        async with IdentityUnitOfWork(self._engine) as uow:
            user = await SQLAlchemyUserRepository(uow).get_by_id(user_id)
            if user is None or user.status != UserStatus.active:
                raise AuthenticationError("Authentication required")

            result = await uow.session.execute(
                text(
                    """
                    SELECT id, workspace_id, email, role, status, expires_at
                    FROM identity.workspace_invites
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
                        UPDATE identity.workspace_invites
                        SET status = 'expired', updated_at = :now
                        WHERE id = :invite_id
                        """
                    ),
                    {"invite_id": invite_id, "now": datetime.now(UTC)},
                )
                raise ConflictError("Invite has expired")

            workspace_id = UUID(str(invite["workspace_id"]))
            role = MemberRole(str(invite["role"]))
            existing = await SQLAlchemyWorkspaceMemberRepository(uow).get_by_workspace_and_user(
                workspace_id,
                user.id,
            )
            joined_at = datetime.now(UTC)
            member_id: UUID
            membership_changed = False
            if existing is None:
                member = await SQLAlchemyWorkspaceMemberRepository(uow).save(
                    WorkspaceMember(
                        user_id=user.id,
                        workspace_id=workspace_id,
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
                            UPDATE identity.workspace_members
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
                    INSERT INTO core.project_members
                        (id, project_id, user_id, status, granted_by_user_id,
                         created_at, updated_at)
                    SELECT gen_random_uuid(), pia.project_id, :user_id, 'active',
                           pia.granted_by_user_id, :now, :now
                    FROM core.project_invite_access AS pia
                    JOIN core.projects AS p ON p.id = pia.project_id
                    WHERE pia.workspace_invite_id = :invite_id
                      AND pia.status = 'pending'
                      AND p.workspace_id = :workspace_id
                    ON CONFLICT (project_id, user_id)
                    DO UPDATE SET status = 'active',
                                  granted_by_user_id = EXCLUDED.granted_by_user_id,
                                  updated_at = EXCLUDED.updated_at
                    """
                ),
                {
                    "user_id": user.id,
                    "invite_id": invite_id,
                    "workspace_id": workspace_id,
                    "now": now,
                },
            )
            await uow.session.execute(
                text(
                    """
                    UPDATE core.project_invite_access
                    SET status = 'applied', updated_at = :now
                    WHERE workspace_invite_id = :invite_id
                      AND status = 'pending'
                    """
                ),
                {"invite_id": invite_id, "now": now},
            )
            await uow.session.execute(
                text(
                    """
                    UPDATE identity.workspace_invites
                    SET status = 'accepted', accepted_at = :now, updated_at = :now
                    WHERE id = :invite_id
                    """
                ),
                {"invite_id": invite_id, "now": now},
            )

            if membership_changed:
                await SQLAlchemyOutboxEventWriter(uow).write(
                    aggregate_type="workspace_member",
                    aggregate_id=member_id,
                    event_type="workspace.member_added.v1",
                    payload={
                        "user_id": str(user.id),
                        "workspace_id": str(workspace_id),
                        "role": role.value,
                    },
                    routing_key="workspace.member_added.v1",
                    idempotency_key=f"identity:workspace.member_added.v1:{member_id}",
                )

            workspace = await SQLAlchemyWorkspaceRepository(uow).get_by_id(workspace_id)
            if workspace is None:
                raise NotFoundError("Workspace not found")
            return workspace

    async def _create_owned_workspace(
        self,
        uow: IdentityUnitOfWork,
        *,
        user_id: UUID,
        name: str,
        slug: str,
    ) -> Workspace:
        if await SQLAlchemyWorkspaceRepository(uow).get_by_slug(slug):
            raise ConflictError(f"Workspace with slug '{slug}' already exists")

        workspace = await SQLAlchemyWorkspaceRepository(uow).save(
            Workspace(name=name, slug=slug)
        )
        await SQLAlchemyOutboxEventWriter(uow).write(
            aggregate_type="workspace",
            aggregate_id=workspace.id,
            event_type="workspace.created.v1",
            payload={"name": workspace.name, "slug": workspace.slug},
            routing_key="workspace.created.v1",
            idempotency_key=f"identity:workspace.created.v1:{workspace.id}",
        )

        member = await SQLAlchemyWorkspaceMemberRepository(uow).save(
            WorkspaceMember(
                user_id=user_id,
                workspace_id=workspace.id,
                role=MemberRole.owner,
                joined_at=datetime.now(UTC),
            )
        )
        await SQLAlchemyOutboxEventWriter(uow).write(
            aggregate_type="workspace_member",
            aggregate_id=member.id,
            event_type="workspace.member_added.v1",
            payload={
                "user_id": str(user_id),
                "workspace_id": str(workspace.id),
                "role": member.role.value,
            },
            routing_key="workspace.member_added.v1",
            idempotency_key=f"identity:workspace.member_added.v1:{member.id}",
        )
        return workspace

    def _authentication_result(
        self,
        user: User,
        session_id: UUID,
        refresh_secret: str,
        *,
        workspace: Workspace | None = None,
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
            workspace=(
                AuthenticatedWorkspace(
                    id=workspace.id,
                    name=workspace.name,
                    slug=workspace.slug,
                    status=workspace.status.value,
                )
                if workspace is not None
                else None
            ),
        )

