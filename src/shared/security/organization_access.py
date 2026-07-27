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
