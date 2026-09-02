from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from uuid import UUID

import uuid6
from sqlalchemy import bindparam, select, text

from modules.identity.application.auth_types import (
    AcceptedWorkspaceInvite,
    IssuedSession,
    SessionRotation,
)
from modules.identity.application.interfaces.authentication import (
    AuthenticationRepository,
    AuthenticationSessionRepository,
)
from modules.identity.domain.entities import User, WorkspaceInvite
from modules.identity.domain.enums import InviteStatus, MemberRole
from modules.identity.infra.database.mappers import (
    workspace_invite_model_to_entity,
    workspace_model_to_entity,
)
from modules.identity.infra.database.models import (
    UserSessionModel,
    WorkspaceInviteModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from shared.contracts.errors import ConflictError, NotFoundError
from shared.security.refresh_tokens import generate_refresh_token, hash_refresh_token


class SQLAlchemyAuthenticationSessionRepository(AuthenticationSessionRepository):
    def __init__(self, uow: IdentityUnitOfWork, *, ttl_days: int) -> None:
        self._uow = uow
        self._ttl_days = ttl_days

    async def issue(
        self,
        *,
        user_id: UUID,
        user_agent: str | None,
        ip_address: str | None,
    ) -> IssuedSession:
        now = datetime.now(UTC)
        session_id = uuid6.uuid7()
        secret = generate_refresh_token()
        model = UserSessionModel(
            id=session_id,
            user_id=user_id,
            refresh_token_hash=hash_refresh_token(secret),
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=now + timedelta(days=self._ttl_days),
            last_used_at=now,
        )
        self._uow.session.add(model)
        await self._uow.session.flush()
        return IssuedSession(id=session_id, user_id=user_id, secret=secret)

    async def rotate(
        self,
        *,
        session_id: UUID,
        secret: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> SessionRotation:
        now = datetime.now(UTC)
        model = await self._uow.session.get(
            UserSessionModel,
            session_id,
            with_for_update=True,
        )
        if model is None or not compare_digest(
            model.refresh_token_hash,
            hash_refresh_token(secret),
        ):
            return SessionRotation(error="Invalid refresh session")

        if model.revoked_at is not None or model.replaced_by_session_id is not None:
            await self.revoke_all(model.user_id)
            return SessionRotation(error="Refresh session reuse detected")
        if self._as_utc(model.expires_at) <= now:
            model.revoked_at = now
            model.updated_at = now
            return SessionRotation(error="Refresh session expired")

        replacement = await self.issue(
            user_id=model.user_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        model.replaced_by_session_id = replacement.id
        model.last_used_at = now
        model.updated_at = now
        return SessionRotation(session=replacement)

    async def revoke(
        self,
        *,
        session_id: UUID | None,
        secret: str | None,
    ) -> None:
        if session_id is None or secret is None:
            return
        model = await self._uow.session.get(
            UserSessionModel,
            session_id,
            with_for_update=True,
        )
        if model is None or not compare_digest(
            model.refresh_token_hash,
            hash_refresh_token(secret),
        ):
            return
        now = datetime.now(UTC)
        model.revoked_at = model.revoked_at or now
        model.updated_at = now

    async def revoke_all(self, user_id: UUID) -> None:
        now = datetime.now(UTC)
        result = await self._uow.session.execute(
            select(UserSessionModel).where(UserSessionModel.user_id == user_id)
        )
        for model in result.scalars().all():
            if model.revoked_at is None:
                model.revoked_at = now
                model.updated_at = now

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class SQLAlchemyAuthenticationRepository(AuthenticationRepository):
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self._uow = uow

    async def list_workspaces(self, user_id: UUID) -> list[dict[str, object]]:
        result = await self._uow.session.execute(
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

    async def list_pending_invites(self, email: str) -> list[dict[str, object]]:
        result = await self._uow.session.execute(
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
            {"email": email.strip().lower()},
        )
        return [dict(row) for row in result.mappings().all()]

    async def create_invite(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        email: str,
        role: MemberRole,
        project_ids: list[UUID],
        expires_at: datetime,
        now: datetime,
    ) -> WorkspaceInvite:
        unique_project_ids = list(dict.fromkeys(project_ids))
        if unique_project_ids:
            project_query = text(
                """
                SELECT id
                FROM core.projects
                WHERE workspace_id = :workspace_id
                  AND id IN :project_ids
                """
            ).bindparams(bindparam("project_ids", expanding=True))
            project_result = await self._uow.session.execute(
                project_query,
                {
                    "workspace_id": workspace_id,
                    "project_ids": unique_project_ids,
                },
            )
            valid_project_ids = {UUID(str(row[0])) for row in project_result.all()}
            if valid_project_ids != set(unique_project_ids):
                raise NotFoundError(
                    "One or more Projects do not belong to this Workspace"
                )

        normalized_email = email.strip().lower()
        result = await self._uow.session.execute(
            select(WorkspaceInviteModel)
            .where(
                WorkspaceInviteModel.workspace_id == workspace_id,
                WorkspaceInviteModel.email == normalized_email,
            )
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is not None and model.status == InviteStatus.pending.value:
            raise ConflictError("A pending invite already exists for this email")

        if model is None:
            model = WorkspaceInviteModel(
                id=uuid6.uuid7(),
                workspace_id=workspace_id,
                email=normalized_email,
                role=role.value,
                token_hash="",
                invited_by_user_id=actor_user_id,
                status=InviteStatus.pending.value,
                expires_at=expires_at,
            )
            self._uow.session.add(model)
        else:
            model.role = role.value
            model.status = InviteStatus.pending.value
            model.invited_by_user_id = actor_user_id
            model.expires_at = expires_at
            model.accepted_at = None
            model.updated_at = now
        await self._uow.session.flush()
        await self._uow.session.refresh(model)

        await self._uow.session.execute(
            text(
                """
                UPDATE core.project_invite_access
                SET status = 'cancelled', updated_at = :now
                WHERE workspace_invite_id = :invite_id
                  AND status = 'pending'
                """
            ),
            {"invite_id": model.id, "now": now},
        )
        for project_id in unique_project_ids:
            await self._uow.session.execute(
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
                    "invite_id": model.id,
                    "actor_user_id": actor_user_id,
                    "now": now,
                },
            )
        return workspace_invite_model_to_entity(model)

    async def accept_invite(
        self,
        *,
        user: User,
        invite_id: UUID,
        now: datetime,
    ) -> AcceptedWorkspaceInvite:
        invite_result = await self._uow.session.execute(
            select(WorkspaceInviteModel)
            .where(WorkspaceInviteModel.id == invite_id)
            .with_for_update()
        )
        invite = invite_result.scalar_one_or_none()
        if invite is None:
            raise NotFoundError("Invite not found")
        if invite.status != InviteStatus.pending.value:
            raise ConflictError("Invite is no longer pending")
        if invite.email.strip().lower() != user.email.strip().lower():
            raise NotFoundError("Invite not found")
        expires_at = invite.expires_at
        if expires_at is not None and self._as_utc(expires_at) <= now:
            raise ConflictError("Invite has expired")

        role = MemberRole(invite.role)
        member_result = await self._uow.session.execute(
            select(WorkspaceMemberModel)
            .where(
                WorkspaceMemberModel.workspace_id == invite.workspace_id,
                WorkspaceMemberModel.user_id == user.id,
            )
            .with_for_update()
        )
        member = member_result.scalar_one_or_none()
        membership_changed = False
        if member is None:
            member = WorkspaceMemberModel(
                id=uuid6.uuid7(),
                user_id=user.id,
                workspace_id=invite.workspace_id,
                role=role.value,
                status="active",
                joined_at=now,
            )
            self._uow.session.add(member)
            membership_changed = True
        elif member.status != "active" or member.role != role.value:
            member.role = role.value
            member.status = "active"
            member.joined_at = now
            member.updated_at = now
            membership_changed = True
        await self._uow.session.flush()

        await self._uow.session.execute(
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
                "workspace_id": invite.workspace_id,
                "now": now,
            },
        )
        await self._uow.session.execute(
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
        invite.status = InviteStatus.accepted.value
        invite.accepted_at = now
        invite.updated_at = now

        workspace = await self._uow.session.get(WorkspaceModel, invite.workspace_id)
        if workspace is None:
            raise NotFoundError("Workspace not found")
        return AcceptedWorkspaceInvite(
            workspace=workspace_model_to_entity(workspace),
            member_id=member.id,
            membership_changed=membership_changed,
            role=role,
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
