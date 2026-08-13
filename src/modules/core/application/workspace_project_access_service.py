from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import uuid6
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.errors import AuthorizationError, ConflictError, NotFoundError


class ProjectAccessService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_accessible_projects(self, *, user_id: UUID, workspace_id: UUID) -> list[dict[str, object]]:
        async with self._session_factory() as session:
            if await self._is_admin(session, user_id):
                result = await session.execute(text("""
                    SELECT id, workspace_id, name, slug, status, created_at, updated_at,
                           'instance_admin' AS access_source
                    FROM core.projects
                    WHERE workspace_id = :workspace_id
                    ORDER BY created_at DESC
                """), {"workspace_id": workspace_id})
            else:
                await self._require_workspace_member(session, user_id, workspace_id)
                result = await session.execute(text("""
                    SELECT p.id, p.workspace_id, p.name, p.slug, p.status,
                           p.created_at, p.updated_at, 'project_membership' AS access_source
                    FROM core.projects p
                    JOIN core.project_members pm ON pm.project_id = p.id
                    WHERE p.workspace_id = :workspace_id
                      AND pm.user_id = :user_id
                      AND pm.status = 'active'
                    ORDER BY p.created_at DESC
                """), {"workspace_id": workspace_id, "user_id": user_id})
            return [dict(row) for row in result.mappings().all()]

    async def list_project_members(self, *, user_id: UUID, project_id: UUID) -> dict[str, object]:
        async with self._session_factory() as session:
            await self._require_admin(session, user_id)
            workspace_id = await self._project_workspace(session, project_id)
            result = await session.execute(text("""
                SELECT u.id AS user_id, u.email,
                       CASE WHEN pm.status = 'active' THEN 'active' ELSE 'none' END AS project_access
                FROM core.workspace_members wm
                JOIN identity.users u ON u.id = wm.user_id
                LEFT JOIN core.project_members pm
                  ON pm.project_id = :project_id AND pm.user_id = wm.user_id
                WHERE wm.workspace_id = :workspace_id
                  AND wm.status = 'active'
                  AND u.status = 'active'
                ORDER BY lower(u.email)
            """), {"project_id": project_id, "workspace_id": workspace_id})
            return {"subjects": [dict(row) for row in result.mappings().all()], "can_manage": True}

    async def grant_project_access(
        self, *, actor_user_id: UUID, project_id: UUID, email: str
    ) -> dict[str, object]:
        async with self._session_factory() as session:
            await self._require_admin(session, actor_user_id)
            workspace_id = await self._project_workspace(session, project_id)
            target = await session.execute(text("""
                SELECT u.id
                FROM identity.users u
                JOIN core.workspace_members wm ON wm.user_id = u.id
                WHERE wm.workspace_id = :workspace_id
                  AND wm.status = 'active'
                  AND lower(u.email) = :email
                  AND u.status = 'active'
            """), {"workspace_id": workspace_id, "email": email.strip().lower()})
            user_id = target.scalar_one_or_none()
            if user_id is None:
                raise ConflictError("User must belong to the Project Workspace")
            now = datetime.now(UTC)
            result = await session.execute(text("""
                INSERT INTO core.project_members
                    (id, project_id, user_id, status, granted_by_user_id, created_at, updated_at)
                VALUES (:id, :project_id, :user_id, 'active', :actor_id, :now, :now)
                ON CONFLICT (project_id, user_id)
                DO UPDATE SET status = 'active',
                              granted_by_user_id = EXCLUDED.granted_by_user_id,
                              updated_at = EXCLUDED.updated_at
                RETURNING id
            """), {"id": uuid6.uuid7(), "project_id": project_id, "user_id": user_id, "actor_id": actor_user_id, "now": now})
            access_id = result.scalar_one()
            await session.commit()
            return {"user_id": user_id, "project_access": "active", "access_id": access_id}

    async def revoke_project_access(
        self, *, actor_user_id: UUID, project_id: UUID, target_user_id: UUID
    ) -> None:
        async with self._session_factory() as session:
            await self._require_admin(session, actor_user_id)
            workspace_id = await self._project_workspace(session, project_id)
            membership = await session.execute(text("""
                SELECT 1 FROM core.workspace_members
                WHERE workspace_id = :workspace_id
                  AND user_id = :user_id
                  AND status = 'active'
            """), {"workspace_id": workspace_id, "user_id": target_user_id})
            if membership.scalar_one_or_none() is None:
                raise NotFoundError("Project access not found")
            result = await session.execute(text("""
                UPDATE core.project_members
                SET status = 'removed', updated_at = :now
                WHERE project_id = :project_id
                  AND user_id = :user_id
                  AND status = 'active'
                RETURNING id
            """), {"project_id": project_id, "user_id": target_user_id, "now": datetime.now(UTC)})
            if result.scalar_one_or_none() is None:
                raise NotFoundError("Project access not found")
            await session.commit()

    async def grant_pending_invite_access(
        self, *, actor_user_id: UUID, project_id: UUID, invite_id: UUID
    ) -> dict[str, object]:
        async with self._session_factory() as session:
            await self._require_admin(session, actor_user_id)
            workspace_id = await self._project_workspace(session, project_id)
            invite = await session.execute(text("""
                SELECT 1 FROM identity.user_invites
                WHERE id = :invite_id
                  AND workspace_id = :workspace_id
                  AND status = 'pending'
                  AND expires_at > now()
            """), {"invite_id": invite_id, "workspace_id": workspace_id})
            if invite.scalar_one_or_none() is None:
                raise ConflictError("Invite must belong to the Project Workspace")
            now = datetime.now(UTC)
            result = await session.execute(text("""
                INSERT INTO core.project_invite_access
                    (id, project_id, user_invite_id, status, granted_by_user_id, created_at, updated_at)
                VALUES (:id, :project_id, :invite_id, 'pending', :actor_id, :now, :now)
                ON CONFLICT (project_id, user_invite_id)
                DO UPDATE SET status = 'pending', updated_at = EXCLUDED.updated_at
                RETURNING id
            """), {"id": uuid6.uuid7(), "project_id": project_id, "invite_id": invite_id, "actor_id": actor_user_id, "now": now})
            access_id = result.scalar_one()
            await session.commit()
            return {"invite_id": invite_id, "project_access": "pending", "access_id": access_id}

    @staticmethod
    async def _is_admin(session: AsyncSession, user_id: UUID) -> bool:
        result = await session.execute(text("""
            SELECT 1 FROM identity.instance_settings
            WHERE id = 1 AND admin_user_id = :user_id AND initialized_at IS NOT NULL
        """), {"user_id": user_id})
        return result.scalar_one_or_none() is not None

    @classmethod
    async def _require_admin(cls, session: AsyncSession, user_id: UUID) -> None:
        if not await cls._is_admin(session, user_id):
            raise AuthorizationError("Instance admin access is required")

    @staticmethod
    async def _project_workspace(session: AsyncSession, project_id: UUID) -> UUID:
        result = await session.execute(
            text("SELECT workspace_id FROM core.projects WHERE id = :project_id"),
            {"project_id": project_id},
        )
        workspace_id = result.scalar_one_or_none()
        if workspace_id is None:
            raise NotFoundError("Project not found")
        return UUID(str(workspace_id))

    @staticmethod
    async def _require_workspace_member(session: AsyncSession, user_id: UUID, workspace_id: UUID) -> None:
        result = await session.execute(text("""
            SELECT 1 FROM core.workspace_members
            WHERE workspace_id = :workspace_id
              AND user_id = :user_id
              AND status = 'active'
        """), {"workspace_id": workspace_id, "user_id": user_id})
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Workspace not found")
