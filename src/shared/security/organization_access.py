from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.errors import AuthorizationError, ConflictError, NotFoundError


class OrganizationAccessService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def require_admin(self, user_id: UUID, organization_id: UUID) -> str:
        async with self._session_factory() as session:
            role = await self._role(session, user_id, organization_id)
            if role not in {"owner", "admin"}:
                raise AuthorizationError("Organization owner or admin access is required")
            return role

    async def require_role_assignment(
        self,
        *,
        actor_user_id: UUID,
        organization_id: UUID,
        target_role: str,
    ) -> str:
        actor_role = await self.require_admin(actor_user_id, organization_id)
        normalized_target = target_role.strip().lower()
        if normalized_target == "owner":
            raise AuthorizationError("Organization ownership cannot be granted through membership or invite")
        if actor_role == "admin" and normalized_target not in {"member", "viewer"}:
            raise AuthorizationError("Organization admins cannot grant administrative roles")
        if normalized_target not in {"admin", "member", "viewer"}:
            raise AuthorizationError("Unsupported organization member role")
        return actor_role

    async def list_members(
        self,
        *,
        actor_user_id: UUID,
        organization_id: UUID,
    ) -> list[dict[str, object]]:
        async with self._session_factory() as session:
            await self._role(session, actor_user_id, organization_id)
            result = await session.execute(
                text(
                    """
                    SELECT om.id, om.user_id, om.organization_id, u.email,
                           om.role, om.status, om.joined_at,
                           CASE
                               WHEN om.role = 'owner' THEN 'implicit_owner'
                               ELSE 'assigned_projects'
                           END AS access_mode,
                           CASE
                               WHEN om.role = 'owner' THEN (
                                   SELECT COUNT(*)
                                   FROM core.projects AS p
                                   WHERE p.organization_id = om.organization_id
                               )
                               ELSE (
                                   SELECT COUNT(*)
                                   FROM core.project_members AS pm
                                   JOIN core.projects AS p ON p.id = pm.project_id
                                   WHERE pm.user_id = om.user_id
                                     AND pm.status = 'active'
                                     AND p.organization_id = om.organization_id
                               )
                           END AS project_access_count
                    FROM identity.organization_members AS om
                    JOIN identity.users AS u ON u.id = om.user_id
                    WHERE om.organization_id = :organization_id
                      AND om.status = 'active'
                    ORDER BY CASE om.role
                               WHEN 'owner' THEN 0
                               WHEN 'admin' THEN 1
                               ELSE 2
                             END,
                             lower(u.email)
                    """
                ),
                {"organization_id": organization_id},
            )
            return [dict(row) for row in result.mappings().all()]

    async def list_invites(
        self,
        *,
        actor_user_id: UUID,
        organization_id: UUID,
    ) -> list[dict[str, object]]:
        async with self._session_factory() as session:
            actor_role = await self._role(session, actor_user_id, organization_id)
            if actor_role not in {"owner", "admin"}:
                raise AuthorizationError("Organization owner or admin access is required")
            result = await session.execute(
                text(
                    """
                    SELECT i.id, i.organization_id, i.email, i.role, i.status,
                           i.expires_at, i.created_at, i.accepted_at,
                           COALESCE(
                               array_agg(pia.project_id ORDER BY p.name)
                               FILTER (WHERE pia.status = 'pending'),
                               ARRAY[]::uuid[]
                           ) AS project_ids,
                           COUNT(pia.id) FILTER (WHERE pia.status = 'pending') AS project_count
                    FROM identity.organization_invites AS i
                    LEFT JOIN core.project_invite_access AS pia
                      ON pia.organization_invite_id = i.id
                    LEFT JOIN core.projects AS p ON p.id = pia.project_id
                    WHERE i.organization_id = :organization_id
                    GROUP BY i.id
                    ORDER BY CASE i.status WHEN 'pending' THEN 0 ELSE 1 END,
                             i.created_at DESC
                    """
                ),
                {"organization_id": organization_id},
            )
            return [dict(row) for row in result.mappings().all()]

    async def remove_member(
        self,
        *,
        actor_user_id: UUID,
        organization_id: UUID,
        target_user_id: UUID,
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            actor_role = await self._role(session, actor_user_id, organization_id)
            if actor_role not in {"owner", "admin"}:
                raise AuthorizationError("Organization owner or admin access is required")
            if actor_user_id == target_user_id:
                raise ConflictError("Use a dedicated leave flow to remove your own membership")

            target_result = await session.execute(
                text(
                    """
                    SELECT om.id, om.role, u.email
                    FROM identity.organization_members AS om
                    JOIN identity.users AS u ON u.id = om.user_id
                    WHERE om.organization_id = :organization_id
                      AND om.user_id = :target_user_id
                      AND om.status = 'active'
                    FOR UPDATE
                    """
                ),
                {
                    "organization_id": organization_id,
                    "target_user_id": target_user_id,
                },
            )
            target = target_result.mappings().first()
            if target is None:
                raise NotFoundError("Organization member not found")

            target_role = str(target["role"])
            if target_role == "owner":
                raise ConflictError("Organization owner membership cannot be removed")
            if actor_role == "admin" and target_role == "admin":
                raise AuthorizationError("Organization admins cannot remove other admins")

            await session.execute(
                text(
                    """
                    UPDATE identity.organization_members
                    SET status = 'removed', updated_at = :now
                    WHERE id = :member_id
                    """
                ),
                {"member_id": target["id"], "now": now},
            )
            project_access_result = await session.execute(
                text(
                    """
                    UPDATE core.project_members AS pm
                    SET status = 'removed', updated_at = :now
                    FROM core.projects AS p
                    WHERE pm.project_id = p.id
                      AND p.organization_id = :organization_id
                      AND pm.user_id = :target_user_id
                      AND pm.status = 'active'
                    RETURNING pm.id
                    """
                ),
                {
                    "organization_id": organization_id,
                    "target_user_id": target_user_id,
                    "now": now,
                },
            )
            project_accesses_removed = len(project_access_result.all())

            pending_access_result = await session.execute(
                text(
                    """
                    UPDATE core.project_invite_access AS pia
                    SET status = 'cancelled', updated_at = :now
                    FROM identity.organization_invites AS i
                    WHERE pia.organization_invite_id = i.id
                      AND i.organization_id = :organization_id
                      AND lower(i.email) = :email
                      AND pia.status = 'pending'
                    RETURNING pia.id
                    """
                ),
                {
                    "organization_id": organization_id,
                    "email": str(target["email"]).strip().lower(),
                    "now": now,
                },
            )
            pending_accesses_cancelled = len(pending_access_result.all())
            await session.execute(
                text(
                    """
                    UPDATE identity.organization_invites
                    SET status = 'revoked', updated_at = :now
                    WHERE organization_id = :organization_id
                      AND lower(email) = :email
                      AND status = 'pending'
                    """
                ),
                {
                    "organization_id": organization_id,
                    "email": str(target["email"]).strip().lower(),
                    "now": now,
                },
            )
            await session.commit()
            return {
                "organization_membership_removed": True,
                "project_accesses_removed": project_accesses_removed,
                "pending_accesses_cancelled": pending_accesses_cancelled,
            }

    async def cancel_invite(
        self,
        *,
        actor_user_id: UUID,
        organization_id: UUID,
        invite_id: UUID,
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            actor_role = await self._role(session, actor_user_id, organization_id)
            if actor_role not in {"owner", "admin"}:
                raise AuthorizationError("Organization owner or admin access is required")

            invite_result = await session.execute(
                text(
                    """
                    SELECT id, role, status
                    FROM identity.organization_invites
                    WHERE id = :invite_id
                      AND organization_id = :organization_id
                    FOR UPDATE
                    """
                ),
                {"invite_id": invite_id, "organization_id": organization_id},
            )
            invite = invite_result.mappings().first()
            if invite is None:
                raise NotFoundError("Invite not found")
            if str(invite["status"]) != "pending":
                raise ConflictError("Only pending invitations can be cancelled")
            if actor_role == "admin" and str(invite["role"]) == "admin":
                raise AuthorizationError("Organization admins cannot cancel admin invitations")

            cancelled_result = await session.execute(
                text(
                    """
                    UPDATE core.project_invite_access
                    SET status = 'cancelled', updated_at = :now
                    WHERE organization_invite_id = :invite_id
                      AND status = 'pending'
                    RETURNING id
                    """
                ),
                {"invite_id": invite_id, "now": now},
            )
            cancelled_count = len(cancelled_result.all())
            await session.execute(
                text(
                    """
                    UPDATE identity.organization_invites
                    SET status = 'revoked', updated_at = :now
                    WHERE id = :invite_id
                    """
                ),
                {"invite_id": invite_id, "now": now},
            )
            await session.commit()
            return {
                "invite_cancelled": True,
                "pending_accesses_cancelled": cancelled_count,
            }

    async def require_valid_invite_acceptance(
        self,
        *,
        user_id: UUID,
        invite_id: UUID,
    ) -> None:
        """Reject stale privileged invites created before role enforcement existed."""
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT i.organization_id, i.email, i.role, i.invited_by_user_id,
                           i.status, u.email AS user_email
                    FROM identity.organization_invites AS i
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
                raise AuthorizationError("Organization ownership cannot be granted through an invitation")
            if target_role not in {"admin", "member", "viewer"}:
                raise AuthorizationError("Unsupported organization invite role")

            inviter_role_result = await session.execute(
                text(
                    """
                    SELECT role
                    FROM identity.organization_members
                    WHERE organization_id = :organization_id
                      AND user_id = :invited_by_user_id
                      AND status = 'active'
                    """
                ),
                {
                    "organization_id": invite["organization_id"],
                    "invited_by_user_id": invite["invited_by_user_id"],
                },
            )
            inviter_role = inviter_role_result.scalar_one_or_none()
            inviter_role = str(inviter_role) if inviter_role is not None else None
            if target_role == "admin" and inviter_role != "owner":
                raise AuthorizationError("Only an Organization owner can grant admin membership")
            if target_role in {"member", "viewer"} and inviter_role not in {"owner", "admin"}:
                raise AuthorizationError("Invite issuer is no longer authorized")

    async def _role(
        self,
        session: AsyncSession,
        user_id: UUID,
        organization_id: UUID,
    ) -> str:
        result = await session.execute(
            text(
                """
                SELECT role
                FROM identity.organization_members
                WHERE user_id = :user_id
                  AND organization_id = :organization_id
                  AND status = 'active'
                """
            ),
            {"user_id": user_id, "organization_id": organization_id},
        )
        role = result.scalar_one_or_none()
        if role is None:
            raise NotFoundError("Resource not found")
        return str(role)
