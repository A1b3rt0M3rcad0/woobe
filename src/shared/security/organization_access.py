from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.errors import AuthorizationError, NotFoundError


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
