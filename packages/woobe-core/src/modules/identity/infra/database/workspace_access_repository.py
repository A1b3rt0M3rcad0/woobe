from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text

from modules.identity.application.interfaces.workspace_access import WorkspaceAccessRepository
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from shared.contracts.errors import AuthorizationError, ConflictError, NotFoundError


class SQLAlchemyWorkspaceAccessRepository(WorkspaceAccessRepository):
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self._uow = uow

    async def require_admin(self, user_id: UUID, workspace_id: UUID) -> str:
        role = await self._role(user_id, workspace_id)
        if role not in {"owner", "admin"}:
            raise AuthorizationError("Workspace owner or admin access is required")
        return role

    async def require_role_assignment(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        target_role: str,
    ) -> str:
        actor_role = await self.require_admin(actor_user_id, workspace_id)
        normalized_target = target_role.strip().lower()
        if normalized_target == "owner":
            raise AuthorizationError(
                "Workspace ownership cannot be granted through membership or invite"
            )
        if actor_role == "admin" and normalized_target not in {"member", "viewer"}:
            raise AuthorizationError(
                "Workspace admins cannot grant administrative roles"
            )
        if normalized_target not in {"admin", "member", "viewer"}:
            raise AuthorizationError("Unsupported workspace member role")
        return actor_role

    async def require_valid_invite_acceptance(
        self,
        *,
        user_id: UUID,
        invite_id: UUID,
    ) -> None:
        result = await self._uow.session.execute(
            text(
                """
                SELECT i.workspace_id, i.email, i.role, i.invited_by_user_id,
                       i.status, u.email AS user_email
                FROM identity.workspace_invites AS i
                JOIN identity.users AS u ON u.id = :user_id
                WHERE i.id = :invite_id
                """
            ),
            {"user_id": user_id, "invite_id": invite_id},
        )
        invite = result.mappings().first()
        if invite is None:
            raise NotFoundError("Invite not found")
        if str(invite["email"]).strip().lower() != str(invite["user_email"]).strip().lower():
            raise NotFoundError("Invite not found")

        target_role = str(invite["role"]).strip().lower()
        if target_role == "owner":
            raise AuthorizationError(
                "Workspace ownership cannot be granted through an invitation"
            )
        if target_role not in {"admin", "member", "viewer"}:
            raise AuthorizationError("Unsupported workspace invite role")

        inviter_role_result = await self._uow.session.execute(
            text(
                """
                SELECT role
                FROM identity.workspace_members
                WHERE workspace_id = :workspace_id
                  AND user_id = :invited_by_user_id
                  AND status = 'active'
                """
            ),
            {
                "workspace_id": invite["workspace_id"],
                "invited_by_user_id": invite["invited_by_user_id"],
            },
        )
        inviter_role = inviter_role_result.scalar_one_or_none()
        inviter_role = str(inviter_role) if inviter_role is not None else None
        if target_role == "admin" and inviter_role != "owner":
            raise AuthorizationError(
                "Only a Workspace owner can grant admin membership"
            )
        if target_role in {"member", "viewer"} and inviter_role not in {
            "owner",
            "admin",
        }:
            raise AuthorizationError("Invite issuer is no longer authorized")

    async def list_members(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
    ) -> list[dict[str, object]]:
        await self._role(actor_user_id, workspace_id)
        result = await self._uow.session.execute(
            text(
                """
                SELECT wm.id, wm.user_id, wm.workspace_id, u.email,
                       wm.role, wm.status, wm.joined_at,
                       CASE
                           WHEN wm.role = 'owner' THEN 'implicit_owner'
                           ELSE 'assigned_projects'
                       END AS access_mode,
                       CASE
                           WHEN wm.role = 'owner' THEN (
                               SELECT COUNT(*)
                               FROM core.projects AS p
                               WHERE p.workspace_id = wm.workspace_id
                           )
                           ELSE (
                               SELECT COUNT(*)
                               FROM core.project_members AS pm
                               JOIN core.projects AS p ON p.id = pm.project_id
                               WHERE pm.user_id = wm.user_id
                                 AND pm.status = 'active'
                                 AND p.workspace_id = wm.workspace_id
                           )
                       END AS project_access_count
                FROM identity.workspace_members AS wm
                JOIN identity.users AS u ON u.id = wm.user_id
                WHERE wm.workspace_id = :workspace_id
                  AND wm.status = 'active'
                ORDER BY CASE wm.role
                           WHEN 'owner' THEN 0
                           WHEN 'admin' THEN 1
                           ELSE 2
                         END,
                         lower(u.email)
                """
            ),
            {"workspace_id": workspace_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def remove_member(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        target_user_id: UUID,
    ) -> dict[str, object]:
        actor_role = await self.require_admin(actor_user_id, workspace_id)
        if actor_user_id == target_user_id:
            raise ConflictError(
                "Use a dedicated leave flow to remove your own membership"
            )

        target_result = await self._uow.session.execute(
            text(
                """
                SELECT wm.id, wm.role, u.email
                FROM identity.workspace_members AS wm
                JOIN identity.users AS u ON u.id = wm.user_id
                WHERE wm.workspace_id = :workspace_id
                  AND wm.user_id = :target_user_id
                  AND wm.status = 'active'
                FOR UPDATE
                """
            ),
            {
                "workspace_id": workspace_id,
                "target_user_id": target_user_id,
            },
        )
        target = target_result.mappings().first()
        if target is None:
            raise NotFoundError("Workspace member not found")

        target_role = str(target["role"])
        if target_role == "owner":
            raise ConflictError("Workspace owner membership cannot be removed")
        if actor_role == "admin" and target_role == "admin":
            raise AuthorizationError("Workspace admins cannot remove other admins")

        now = datetime.now(UTC)
        await self._uow.session.execute(
            text(
                """
                UPDATE identity.workspace_members
                SET status = 'removed', updated_at = :now
                WHERE id = :member_id
                """
            ),
            {"member_id": target["id"], "now": now},
        )
        project_access_result = await self._uow.session.execute(
            text(
                """
                UPDATE core.project_members AS pm
                SET status = 'removed', updated_at = :now
                FROM core.projects AS p
                WHERE pm.project_id = p.id
                  AND p.workspace_id = :workspace_id
                  AND pm.user_id = :target_user_id
                  AND pm.status = 'active'
                RETURNING pm.id
                """
            ),
            {
                "workspace_id": workspace_id,
                "target_user_id": target_user_id,
                "now": now,
            },
        )
        project_accesses_removed = len(project_access_result.all())

        pending_access_result = await self._uow.session.execute(
            text(
                """
                UPDATE core.project_invite_access AS pia
                SET status = 'cancelled', updated_at = :now
                FROM identity.workspace_invites AS i
                WHERE pia.workspace_invite_id = i.id
                  AND i.workspace_id = :workspace_id
                  AND lower(i.email) = :email
                  AND pia.status = 'pending'
                RETURNING pia.id
                """
            ),
            {
                "workspace_id": workspace_id,
                "email": str(target["email"]).strip().lower(),
                "now": now,
            },
        )
        pending_accesses_cancelled = len(pending_access_result.all())
        await self._uow.session.execute(
            text(
                """
                UPDATE identity.workspace_invites
                SET status = 'revoked', updated_at = :now
                WHERE workspace_id = :workspace_id
                  AND lower(email) = :email
                  AND status = 'pending'
                """
            ),
            {
                "workspace_id": workspace_id,
                "email": str(target["email"]).strip().lower(),
                "now": now,
            },
        )
        return {
            "workspace_membership_removed": True,
            "project_accesses_removed": project_accesses_removed,
            "pending_accesses_cancelled": pending_accesses_cancelled,
        }

    async def list_invites(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
    ) -> list[dict[str, object]]:
        actor_role = await self._role(actor_user_id, workspace_id)
        if actor_role not in {"owner", "admin"}:
            raise AuthorizationError("Workspace owner or admin access is required")
        result = await self._uow.session.execute(
            text(
                """
                SELECT i.id, i.workspace_id, i.email, i.role, i.status,
                       i.expires_at, i.created_at, i.accepted_at,
                       COALESCE(
                           array_agg(pia.project_id ORDER BY p.name)
                           FILTER (WHERE pia.status = 'pending'),
                           ARRAY[]::uuid[]
                       ) AS project_ids,
                       COUNT(pia.id) FILTER (WHERE pia.status = 'pending') AS project_count
                FROM identity.workspace_invites AS i
                LEFT JOIN core.project_invite_access AS pia
                  ON pia.workspace_invite_id = i.id
                LEFT JOIN core.projects AS p ON p.id = pia.project_id
                WHERE i.workspace_id = :workspace_id
                GROUP BY i.id
                ORDER BY CASE i.status WHEN 'pending' THEN 0 ELSE 1 END,
                         i.created_at DESC
                """
            ),
            {"workspace_id": workspace_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def cancel_invite(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        invite_id: UUID,
    ) -> dict[str, object]:
        actor_role = await self.require_admin(actor_user_id, workspace_id)
        invite_result = await self._uow.session.execute(
            text(
                """
                SELECT id, role, status
                FROM identity.workspace_invites
                WHERE id = :invite_id
                  AND workspace_id = :workspace_id
                FOR UPDATE
                """
            ),
            {"invite_id": invite_id, "workspace_id": workspace_id},
        )
        invite = invite_result.mappings().first()
        if invite is None:
            raise NotFoundError("Invite not found")
        if str(invite["status"]) != "pending":
            raise ConflictError("Only pending invitations can be cancelled")
        if actor_role == "admin" and str(invite["role"]) == "admin":
            raise AuthorizationError("Workspace admins cannot cancel admin invitations")

        now = datetime.now(UTC)
        cancelled_result = await self._uow.session.execute(
            text(
                """
                UPDATE core.project_invite_access
                SET status = 'cancelled', updated_at = :now
                WHERE workspace_invite_id = :invite_id
                  AND status = 'pending'
                RETURNING id
                """
            ),
            {"invite_id": invite_id, "now": now},
        )
        cancelled_count = len(cancelled_result.all())
        await self._uow.session.execute(
            text(
                """
                UPDATE identity.workspace_invites
                SET status = 'revoked', updated_at = :now
                WHERE id = :invite_id
                """
            ),
            {"invite_id": invite_id, "now": now},
        )
        return {
            "invite_cancelled": True,
            "pending_accesses_cancelled": cancelled_count,
        }

    async def _role(self, user_id: UUID, workspace_id: UUID) -> str:
        result = await self._uow.session.execute(
            text(
                """
                SELECT role
                FROM identity.workspace_members
                WHERE user_id = :user_id
                  AND workspace_id = :workspace_id
                  AND status = 'active'
                """
            ),
            {"user_id": user_id, "workspace_id": workspace_id},
        )
        role = result.scalar_one_or_none()
        if role is None:
            raise NotFoundError("Resource not found")
        return str(role)
