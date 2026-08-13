from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import uuid6
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.errors import AuthorizationError, ConflictError, NotFoundError


class WorkspaceService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def is_instance_admin(self, user_id: UUID) -> bool:
        async with self._session_factory() as session:
            return await self._is_instance_admin(session, user_id)

    async def list_accessible(self, user_id: UUID) -> list[dict[str, object]]:
        async with self._session_factory() as session:
            if await self._is_instance_admin(session, user_id):
                result = await session.execute(text("""
                    SELECT id, name, slug, status, created_at, updated_at,
                           true AS can_manage
                    FROM core.workspaces
                    WHERE status = 'active'
                    ORDER BY created_at DESC
                """))
            else:
                result = await session.execute(text("""
                    SELECT w.id, w.name, w.slug, w.status, w.created_at, w.updated_at,
                           false AS can_manage
                    FROM core.workspace_members wm
                    JOIN core.workspaces w ON w.id = wm.workspace_id
                    WHERE wm.user_id = :user_id
                      AND wm.status = 'active'
                      AND w.status = 'active'
                    ORDER BY w.created_at DESC
                """), {"user_id": user_id})
            return [dict(row) for row in result.mappings().all()]

    async def get_accessible(self, user_id: UUID, workspace_id: UUID) -> dict[str, object]:
        async with self._session_factory() as session:
            admin = await self._is_instance_admin(session, user_id)
            if not admin:
                await self._require_membership(session, user_id, workspace_id)
            row = (await session.execute(text("""
                SELECT id, name, slug, status, created_at, updated_at
                FROM core.workspaces
                WHERE id = :workspace_id AND status = 'active'
            """), {"workspace_id": workspace_id})).mappings().first()
            if row is None:
                raise NotFoundError("Workspace not found")
            data = dict(row)
            data["can_manage"] = admin
            return data

    async def create(self, actor_user_id: UUID, name: str, slug: str) -> dict[str, object]:
        normalized_name = name.strip()
        normalized_slug = slug.strip().lower()
        if not normalized_name or not normalized_slug:
            raise ConflictError("Workspace name and slug are required")
        async with self._session_factory() as session:
            await self._require_admin(session, actor_user_id)
            duplicate = await session.execute(
                text("SELECT 1 FROM core.workspaces WHERE slug = :slug"),
                {"slug": normalized_slug},
            )
            if duplicate.scalar_one_or_none() is not None:
                raise ConflictError(f"Workspace with slug '{normalized_slug}' already exists")
            workspace_id = uuid6.uuid7()
            now = datetime.now(UTC)
            result = await session.execute(text("""
                INSERT INTO core.workspaces
                    (id, name, slug, status, created_at, updated_at)
                VALUES (:id, :name, :slug, 'active', :now, :now)
                RETURNING id, name, slug, status, created_at, updated_at
            """), {"id": workspace_id, "name": normalized_name, "slug": normalized_slug, "now": now})
            await session.commit()
            data = dict(result.mappings().one())
            data["can_manage"] = True
            return data

    async def update(
        self,
        actor_user_id: UUID,
        workspace_id: UUID,
        *,
        name: str | None,
        slug: str | None,
    ) -> dict[str, object]:
        async with self._session_factory() as session:
            await self._require_admin(session, actor_user_id)
            current = (await session.execute(text("""
                SELECT name, slug FROM core.workspaces
                WHERE id = :workspace_id AND status = 'active'
            """), {"workspace_id": workspace_id})).mappings().first()
            if current is None:
                raise NotFoundError("Workspace not found")
            next_name = name.strip() if name is not None else str(current["name"])
            next_slug = slug.strip().lower() if slug is not None else str(current["slug"])
            duplicate = await session.execute(text("""
                SELECT 1 FROM core.workspaces
                WHERE slug = :slug AND id <> :workspace_id
            """), {"slug": next_slug, "workspace_id": workspace_id})
            if duplicate.scalar_one_or_none() is not None:
                raise ConflictError(f"Workspace with slug '{next_slug}' already exists")
            result = await session.execute(text("""
                UPDATE core.workspaces
                SET name = :name, slug = :slug, updated_at = :now
                WHERE id = :workspace_id
                RETURNING id, name, slug, status, created_at, updated_at
            """), {"name": next_name, "slug": next_slug, "now": datetime.now(UTC), "workspace_id": workspace_id})
            await session.commit()
            data = dict(result.mappings().one())
            data["can_manage"] = True
            return data

    async def list_members(self, actor_user_id: UUID, workspace_id: UUID) -> list[dict[str, object]]:
        async with self._session_factory() as session:
            await self._require_admin(session, actor_user_id)
            result = await session.execute(text("""
                SELECT wm.user_id, u.email, wm.status, wm.joined_at
                FROM core.workspace_members wm
                JOIN identity.users u ON u.id = wm.user_id
                WHERE wm.workspace_id = :workspace_id
                  AND wm.status = 'active'
                  AND u.status = 'active'
                ORDER BY lower(u.email)
            """), {"workspace_id": workspace_id})
            return [dict(row) for row in result.mappings().all()]

    async def remove_member(self, actor_user_id: UUID, workspace_id: UUID, user_id: UUID) -> None:
        async with self._session_factory() as session:
            await self._require_admin(session, actor_user_id)
            if await self._is_instance_admin(session, user_id):
                raise ConflictError("Instance admin is not a Workspace member")
            result = await session.execute(text("""
                UPDATE core.workspace_members
                SET status = 'removed', updated_at = :now
                WHERE workspace_id = :workspace_id
                  AND user_id = :user_id
                  AND status = 'active'
                RETURNING id
            """), {"workspace_id": workspace_id, "user_id": user_id, "now": datetime.now(UTC)})
            if result.scalar_one_or_none() is None:
                raise NotFoundError("Workspace member not found")
            await session.execute(text("""
                UPDATE core.project_members pm
                SET status = 'removed', updated_at = :now
                FROM core.projects p
                WHERE pm.project_id = p.id
                  AND p.workspace_id = :workspace_id
                  AND pm.user_id = :user_id
                  AND pm.status = 'active'
            """), {"workspace_id": workspace_id, "user_id": user_id, "now": datetime.now(UTC)})
            await session.commit()

    @staticmethod
    async def _is_instance_admin(session: AsyncSession, user_id: UUID) -> bool:
        result = await session.execute(text("""
            SELECT 1 FROM identity.instance_settings
            WHERE id = 1
              AND admin_user_id = :user_id
              AND initialized_at IS NOT NULL
        """), {"user_id": user_id})
        return result.scalar_one_or_none() is not None

    @classmethod
    async def _require_admin(cls, session: AsyncSession, user_id: UUID) -> None:
        if not await cls._is_instance_admin(session, user_id):
            raise AuthorizationError("Only the Instance admin can manage Workspaces")

    @staticmethod
    async def _require_membership(session: AsyncSession, user_id: UUID, workspace_id: UUID) -> None:
        result = await session.execute(text("""
            SELECT 1 FROM core.workspace_members
            WHERE user_id = :user_id
              AND workspace_id = :workspace_id
              AND status = 'active'
        """), {"user_id": user_id, "workspace_id": workspace_id})
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Workspace not found")
