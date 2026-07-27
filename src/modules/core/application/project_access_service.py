from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import uuid6
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.errors import AuthorizationError, ConflictError, NotFoundError


class ProjectAccessService:
    """Simple MVP authorization for Organization membership and full Project access."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def require_organization_admin(self, user_id: UUID, organization_id: UUID) -> str:
        async with self._session_factory() as session:
            role = await self._organization_role(session, user_id, organization_id)
            if role not in {"owner", "admin"}:
                raise AuthorizationError("Organization owner or admin access is required")
            return role

    async def list_accessible_projects(
        self,
        *,
        user_id: UUID,
        organization_id: UUID,
    ) -> list[dict[str, object]]:
        async with self._session_factory() as session:
            role = await self._organization_role(session, user_id, organization_id)
            if role == "owner":
                result = await session.execute(
                    text(
                        """
                        SELECT id, organization_id, name, slug, status, created_at, updated_at
                        FROM core.projects
                        WHERE organization_id = :organization_id
                        ORDER BY created_at DESC
                        """
                    ),
                    {"organization_id": organization_id},
                )
            else:
                result = await session.execute(
                    text(
                        """
                        SELECT p.id, p.organization_id, p.name, p.slug, p.status,
                               p.created_at, p.updated_at
                        FROM core.projects AS p
                        JOIN core.project_members AS pm
                          ON pm.project_id = p.id
                         AND pm.user_id = :user_id
                         AND pm.status = 'active'
                        WHERE p.organization_id = :organization_id
                        ORDER BY p.created_at DESC
                        """
                    ),
                    {"organization_id": organization_id, "user_id": user_id},
                )
            return [dict(row._mapping) for row in result.all()]

    async def list_projects_for_access_management(
        self,
        *,
        user_id: UUID,
        organization_id: UUID,
    ) -> list[dict[str, object]]:
        async with self._session_factory() as session:
            await self._require_organization_admin(session, user_id, organization_id)
            result = await session.execute(
                text(
                    """
                    SELECT p.id, p.organization_id, p.name, p.slug, p.status,
                           p.created_at, p.updated_at,
                           COUNT(pm.id) FILTER (WHERE pm.status = 'active') AS member_count
                    FROM core.projects AS p
                    LEFT JOIN core.project_members AS pm ON pm.project_id = p.id
                    WHERE p.organization_id = :organization_id
                    GROUP BY p.id
                    ORDER BY p.created_at DESC
                    """
                ),
                {"organization_id": organization_id},
            )
            return [dict(row._mapping) for row in result.all()]

    async def list_project_members(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
    ) -> dict[str, object]:
        async with self._session_factory() as session:
            organization_id = await self._project_organization_id(session, project_id)
            role = await self._organization_role(session, user_id, organization_id)
            can_manage = role in {"owner", "admin"}
            if not can_manage:
                await self._require_project_member(session, user_id, project_id)

            owner_result = await session.execute(
                text(
                    """
                    SELECT u.id AS user_id, u.email
                    FROM identity.organization_members AS om
                    JOIN identity.users AS u ON u.id = om.user_id
                    WHERE om.organization_id = :organization_id
                      AND om.status = 'active'
                      AND om.role = 'owner'
                    ORDER BY om.joined_at ASC
                    LIMIT 1
                    """
                ),
                {"organization_id": organization_id},
            )
            owner = owner_result.mappings().first()

            members_result = await session.execute(
                text(
                    """
                    SELECT pm.id, pm.user_id, u.email, pm.status, pm.created_at
                    FROM core.project_members AS pm
                    JOIN identity.users AS u ON u.id = pm.user_id
                    WHERE pm.project_id = :project_id
                      AND pm.status = 'active'
                    ORDER BY pm.created_at ASC
                    """
                ),
                {"project_id": project_id},
            )
            members = [dict(row) for row in members_result.mappings().all()]
            if owner is not None and all(item["user_id"] != owner["user_id"] for item in members):
                members.insert(
                    0,
                    {
                        "id": None,
                        "user_id": owner["user_id"],
                        "email": owner["email"],
                        "status": "active",
                        "created_at": None,
                        "implicit_owner": True,
                    },
                )
            for item in members:
                item.setdefault("implicit_owner", False)
            return {"members": members, "can_manage": can_manage}

    async def grant_project_access(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
        email: str,
    ) -> dict[str, object]:
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise ConflictError("Member email is required")

        async with self._session_factory() as session:
            organization_id = await self._project_organization_id(session, project_id)
            await self._require_organization_admin(session, actor_user_id, organization_id)

            target_result = await session.execute(
                text(
                    """
                    SELECT u.id, u.email, om.role
                    FROM identity.users AS u
                    JOIN identity.organization_members AS om
                      ON om.user_id = u.id
                     AND om.organization_id = :organization_id
                     AND om.status = 'active'
                    WHERE lower(u.email) = :email
                      AND u.status = 'active'
                    """
                ),
                {"organization_id": organization_id, "email": normalized_email},
            )
            target = target_result.mappings().first()
            if target is None:
                raise NotFoundError("User must be an active member of this organization")
            if str(target["role"]) == "owner":
                raise ConflictError("Organization owner already has implicit project access")

            now = datetime.now(UTC)
            existing_result = await session.execute(
                text(
                    """
                    SELECT id
                    FROM core.project_members
                    WHERE project_id = :project_id AND user_id = :user_id
                    """
                ),
                {"project_id": project_id, "user_id": target["id"]},
            )
            existing_id = existing_result.scalar_one_or_none()
            if existing_id is None:
                member_id = uuid6.uuid7()
                await session.execute(
                    text(
                        """
                        INSERT INTO core.project_members
                            (id, project_id, user_id, status, granted_by_user_id, created_at, updated_at)
                        VALUES
                            (:id, :project_id, :user_id, 'active', :granted_by_user_id, :now, :now)
                        """
                    ),
                    {
                        "id": member_id,
                        "project_id": project_id,
                        "user_id": target["id"],
                        "granted_by_user_id": actor_user_id,
                        "now": now,
                    },
                )
            else:
                member_id = existing_id
                await session.execute(
                    text(
                        """
                        UPDATE core.project_members
                        SET status = 'active', granted_by_user_id = :granted_by_user_id,
                            updated_at = :now
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": member_id,
                        "granted_by_user_id": actor_user_id,
                        "now": now,
                    },
                )
            await session.commit()
            return {
                "id": member_id,
                "user_id": target["id"],
                "email": target["email"],
                "status": "active",
                "implicit_owner": False,
            }

    async def revoke_project_access(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
        target_user_id: UUID,
    ) -> None:
        async with self._session_factory() as session:
            organization_id = await self._project_organization_id(session, project_id)
            await self._require_organization_admin(session, actor_user_id, organization_id)
            target_role = await self._organization_role(session, target_user_id, organization_id)
            if target_role == "owner":
                raise ConflictError("Organization owner access cannot be revoked from a project")

            result = await session.execute(
                text(
                    """
                    UPDATE core.project_members
                    SET status = 'removed', updated_at = :updated_at
                    WHERE project_id = :project_id
                      AND user_id = :target_user_id
                      AND status = 'active'
                    RETURNING id
                    """
                ),
                {
                    "project_id": project_id,
                    "target_user_id": target_user_id,
                    "updated_at": datetime.now(UTC),
                },
            )
            if result.scalar_one_or_none() is None:
                raise NotFoundError("Project access not found")
            await session.commit()

    async def ensure_creator_access(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
    ) -> None:
        async with self._session_factory() as session:
            organization_id = await self._project_organization_id(session, project_id)
            role = await self._require_organization_admin(session, actor_user_id, organization_id)
            if role == "owner":
                return
            now = datetime.now(UTC)
            existing = await session.execute(
                text(
                    """
                    SELECT id FROM core.project_members
                    WHERE project_id = :project_id AND user_id = :user_id
                    """
                ),
                {"project_id": project_id, "user_id": actor_user_id},
            )
            member_id = existing.scalar_one_or_none()
            if member_id is None:
                await session.execute(
                    text(
                        """
                        INSERT INTO core.project_members
                            (id, project_id, user_id, status, granted_by_user_id, created_at, updated_at)
                        VALUES
                            (:id, :project_id, :user_id, 'active', :user_id, :now, :now)
                        """
                    ),
                    {
                        "id": uuid6.uuid7(),
                        "project_id": project_id,
                        "user_id": actor_user_id,
                        "now": now,
                    },
                )
            else:
                await session.execute(
                    text(
                        """
                        UPDATE core.project_members
                        SET status = 'active', updated_at = :now
                        WHERE id = :id
                        """
                    ),
                    {"id": member_id, "now": now},
                )
            await session.commit()

    async def _project_organization_id(self, session: AsyncSession, project_id: UUID) -> UUID:
        result = await session.execute(
            text("SELECT organization_id FROM core.projects WHERE id = :project_id"),
            {"project_id": project_id},
        )
        organization_id = result.scalar_one_or_none()
        if organization_id is None:
            raise NotFoundError("Project not found")
        return UUID(str(organization_id))

    async def _organization_role(
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

    async def _require_organization_admin(
        self,
        session: AsyncSession,
        user_id: UUID,
        organization_id: UUID,
    ) -> str:
        role = await self._organization_role(session, user_id, organization_id)
        if role not in {"owner", "admin"}:
            raise AuthorizationError("Organization owner or admin access is required")
        return role

    async def _require_project_member(
        self,
        session: AsyncSession,
        user_id: UUID,
        project_id: UUID,
    ) -> None:
        result = await session.execute(
            text(
                """
                SELECT 1
                FROM core.project_members
                WHERE project_id = :project_id
                  AND user_id = :user_id
                  AND status = 'active'
                """
            ),
            {"project_id": project_id, "user_id": user_id},
        )
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Resource not found")
