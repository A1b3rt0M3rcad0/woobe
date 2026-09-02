from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import uuid6
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from modules.core.application.interfaces.project_access import ProjectAccessRepository
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.contracts.errors import AuthorizationError, ConflictError, NotFoundError


class SQLAlchemyProjectAccessRepository(ProjectAccessRepository):
    """MVP authorization for Workspace membership and full Project access."""

    def __init__(self, uow: CoreUnitOfWork) -> None:
        self._uow = uow

    async def require_workspace_admin(self, user_id: UUID, workspace_id: UUID) -> str:
        session = self._uow.session
        role = await self._workspace_role(session, user_id, workspace_id)
        if role not in {"owner", "admin"}:
            raise AuthorizationError("Workspace owner or admin access is required")
        return role

    async def list_accessible_projects(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> list[dict[str, object]]:
        session = self._uow.session
        role = await self._workspace_role(session, user_id, workspace_id)
        if role == "owner":
            result = await session.execute(
                text(
                    """
                    SELECT id, workspace_id, name, slug, status, created_at, updated_at,
                           :role AS workspace_role,
                           'workspace_owner' AS access_source
                    FROM core.projects
                    WHERE workspace_id = :workspace_id
                    ORDER BY created_at DESC
                    """
                ),
                {"workspace_id": workspace_id, "role": role},
            )
        else:
            result = await session.execute(
                text(
                    """
                    SELECT p.id, p.workspace_id, p.name, p.slug, p.status,
                           p.created_at, p.updated_at,
                           :role AS workspace_role,
                           'project_membership' AS access_source
                    FROM core.projects AS p
                    JOIN core.project_members AS pm
                      ON pm.project_id = p.id
                     AND pm.user_id = :user_id
                     AND pm.status = 'active'
                    WHERE p.workspace_id = :workspace_id
                    ORDER BY p.created_at DESC
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "user_id": user_id,
                    "role": role,
                },
            )
        return [dict(row) for row in result.mappings().all()]

    async def list_projects_for_access_management(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> list[dict[str, object]]:
        session = self._uow.session
        await self._require_workspace_admin(session, user_id, workspace_id)
        result = await session.execute(
            text(
                """
                SELECT p.id, p.workspace_id, p.name, p.slug, p.status,
                       p.created_at, p.updated_at,
                       COUNT(DISTINCT pm.id) FILTER (WHERE pm.status = 'active') AS member_count,
                       COUNT(DISTINCT pia.id) FILTER (WHERE pia.status = 'pending') AS pending_count
                FROM core.projects AS p
                LEFT JOIN core.project_members AS pm ON pm.project_id = p.id
                LEFT JOIN core.project_invite_access AS pia ON pia.project_id = p.id
                WHERE p.workspace_id = :workspace_id
                GROUP BY p.id
                ORDER BY p.created_at DESC
                """
            ),
            {"workspace_id": workspace_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def list_project_members(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
    ) -> dict[str, object]:
        session = self._uow.session
        workspace_id = await self._project_workspace_id(session, project_id)
        role = await self._workspace_role(session, user_id, workspace_id)
        can_manage = role in {"owner", "admin"}
        if not can_manage:
            await self._require_project_member(session, user_id, project_id)

        members_result = await session.execute(
            text(
                """
                SELECT 'member' AS subject_type,
                       u.id AS subject_id,
                       u.id AS user_id,
                       NULL::uuid AS invite_id,
                       u.email,
                       wm.role AS workspace_role,
                       wm.status AS workspace_status,
                       CASE
                           WHEN wm.role = 'owner' THEN 'implicit'
                           WHEN pm.status = 'active' THEN 'active'
                           ELSE 'none'
                       END AS project_access,
                       pm.id AS project_member_id,
                       NULL::uuid AS pending_access_id
                FROM identity.workspace_members AS wm
                JOIN identity.users AS u ON u.id = wm.user_id
                LEFT JOIN core.project_members AS pm
                  ON pm.project_id = :project_id
                 AND pm.user_id = wm.user_id
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
            {"project_id": project_id, "workspace_id": workspace_id},
        )
        subjects = [dict(row) for row in members_result.mappings().all()]

        invites_result = await session.execute(
            text(
                """
                SELECT 'invite' AS subject_type,
                       i.id AS subject_id,
                       NULL::uuid AS user_id,
                       i.id AS invite_id,
                       i.email,
                       i.role AS workspace_role,
                       'pending' AS workspace_status,
                       CASE WHEN pia.status = 'pending' THEN 'pending' ELSE 'none' END AS project_access,
                       NULL::uuid AS project_member_id,
                       pia.id AS pending_access_id
                FROM identity.workspace_invites AS i
                LEFT JOIN core.project_invite_access AS pia
                  ON pia.workspace_invite_id = i.id
                 AND pia.project_id = :project_id
                WHERE i.workspace_id = :workspace_id
                  AND i.status = 'pending'
                  AND i.expires_at > now()
                ORDER BY lower(i.email)
                """
            ),
            {"project_id": project_id, "workspace_id": workspace_id},
        )
        subjects.extend(dict(row) for row in invites_result.mappings().all())
        return {"subjects": subjects, "can_manage": can_manage}

    async def grant_project_subject_access(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
        subject_type: str,
        subject_id: UUID,
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        session = self._uow.session
        workspace_id = await self._project_workspace_id(session, project_id)
        await self._require_workspace_admin(session, actor_user_id, workspace_id)

        if subject_type == "member":
            target_result = await session.execute(
                text(
                    """
                    SELECT u.id, u.email, wm.role
                    FROM identity.users AS u
                    JOIN identity.workspace_members AS wm
                      ON wm.user_id = u.id
                     AND wm.workspace_id = :workspace_id
                     AND wm.status = 'active'
                    WHERE u.id = :subject_id
                      AND u.status = 'active'
                    """
                ),
                {"workspace_id": workspace_id, "subject_id": subject_id},
            )
            target = target_result.mappings().first()
            if target is None:
                raise NotFoundError("Workspace member not found")
            if str(target["role"]) == "owner":
                raise ConflictError("Workspace owner already has implicit Project access")

            member_id = uuid6.uuid7()
            result = await session.execute(
                text(
                    """
                    INSERT INTO core.project_members
                        (id, project_id, user_id, status, granted_by_user_id,
                         created_at, updated_at)
                    VALUES
                        (:id, :project_id, :user_id, 'active', :actor_user_id,
                         :now, :now)
                    ON CONFLICT (project_id, user_id)
                    DO UPDATE SET status = 'active',
                                  granted_by_user_id = EXCLUDED.granted_by_user_id,
                                  updated_at = EXCLUDED.updated_at
                    RETURNING id
                    """
                ),
                {
                    "id": member_id,
                    "project_id": project_id,
                    "user_id": subject_id,
                    "actor_user_id": actor_user_id,
                    "now": now,
                },
            )
            access_id = result.scalar_one()
            return {
                "subject_type": "member",
                "subject_id": subject_id,
                "project_access": "active",
                "access_id": access_id,
            }

        if subject_type == "invite":
            invite_result = await session.execute(
                text(
                    """
                    SELECT id, email
                    FROM identity.workspace_invites
                    WHERE id = :subject_id
                      AND workspace_id = :workspace_id
                      AND status = 'pending'
                      AND expires_at > now()
                    """
                ),
                {"subject_id": subject_id, "workspace_id": workspace_id},
            )
            if invite_result.mappings().first() is None:
                raise NotFoundError("Pending Workspace invite not found")
            pending_id = uuid6.uuid7()
            result = await session.execute(
                text(
                    """
                    INSERT INTO core.project_invite_access
                        (id, project_id, workspace_invite_id, status,
                         granted_by_user_id, created_at, updated_at)
                    VALUES
                        (:id, :project_id, :invite_id, 'pending',
                         :actor_user_id, :now, :now)
                    ON CONFLICT (project_id, workspace_invite_id)
                    DO UPDATE SET status = 'pending',
                                  granted_by_user_id = EXCLUDED.granted_by_user_id,
                                  updated_at = EXCLUDED.updated_at
                    RETURNING id
                    """
                ),
                {
                    "id": pending_id,
                    "project_id": project_id,
                    "invite_id": subject_id,
                    "actor_user_id": actor_user_id,
                    "now": now,
                },
            )
            access_id = result.scalar_one()
            return {
                "subject_type": "invite",
                "subject_id": subject_id,
                "project_access": "pending",
                "access_id": access_id,
            }

        raise ConflictError("Unsupported Project access subject")

    async def revoke_project_subject_access(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
        subject_type: str,
        subject_id: UUID,
    ) -> None:
        now = datetime.now(UTC)
        session = self._uow.session
        workspace_id = await self._project_workspace_id(session, project_id)
        await self._require_workspace_admin(session, actor_user_id, workspace_id)

        if subject_type == "member":
            target_role = await self._workspace_role(session, subject_id, workspace_id)
            if target_role == "owner":
                raise ConflictError("Workspace owner access cannot be revoked from a Project")
            result = await session.execute(
                text(
                    """
                    UPDATE core.project_members
                    SET status = 'removed', updated_at = :updated_at
                    WHERE project_id = :project_id
                      AND user_id = :subject_id
                      AND status = 'active'
                    RETURNING id
                    """
                ),
                {
                    "project_id": project_id,
                    "subject_id": subject_id,
                    "updated_at": now,
                },
            )
        elif subject_type == "invite":
            result = await session.execute(
                text(
                    """
                    UPDATE core.project_invite_access
                    SET status = 'cancelled', updated_at = :updated_at
                    WHERE project_id = :project_id
                      AND workspace_invite_id = :subject_id
                      AND status = 'pending'
                    RETURNING id
                    """
                ),
                {
                    "project_id": project_id,
                    "subject_id": subject_id,
                    "updated_at": now,
                },
            )
        else:
            raise ConflictError("Unsupported Project access subject")

        if result.scalar_one_or_none() is None:
            raise NotFoundError("Project access not found")

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
        session = self._uow.session
        workspace_id = await self._project_workspace_id(session, project_id)
        target_result = await session.execute(
            text(
                """
                SELECT u.id
                FROM identity.users AS u
                JOIN identity.workspace_members AS wm
                  ON wm.user_id = u.id
                 AND wm.workspace_id = :workspace_id
                 AND wm.status = 'active'
                WHERE lower(u.email) = :email
                  AND u.status = 'active'
                """
            ),
            {"workspace_id": workspace_id, "email": normalized_email},
        )
        target_user_id = target_result.scalar_one_or_none()
        if target_user_id is None:
            raise NotFoundError("User must be an active member of this Workspace")
        return await self.grant_project_subject_access(
            actor_user_id=actor_user_id,
            project_id=project_id,
            subject_type="member",
            subject_id=UUID(str(target_user_id)),
        )

    async def revoke_project_access(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
        target_user_id: UUID,
    ) -> None:
        await self.revoke_project_subject_access(
            actor_user_id=actor_user_id,
            project_id=project_id,
            subject_type="member",
            subject_id=target_user_id,
        )

    async def ensure_creator_access(
        self,
        *,
        actor_user_id: UUID,
        project_id: UUID,
    ) -> None:
        session = self._uow.session
        workspace_id = await self._project_workspace_id(session, project_id)
        role = await self._require_workspace_admin(session, actor_user_id, workspace_id)
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

    async def _project_workspace_id(self, session: AsyncSession, project_id: UUID) -> UUID:
        result = await session.execute(
            text("SELECT workspace_id FROM core.projects WHERE id = :project_id"),
            {"project_id": project_id},
        )
        workspace_id = result.scalar_one_or_none()
        if workspace_id is None:
            raise NotFoundError("Project not found")
        return UUID(str(workspace_id))

    async def _workspace_role(
        self,
        session: AsyncSession,
        user_id: UUID,
        workspace_id: UUID,
    ) -> str:
        result = await session.execute(
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

    async def _require_workspace_admin(
        self,
        session: AsyncSession,
        user_id: UUID,
        workspace_id: UUID,
    ) -> str:
        role = await self._workspace_role(session, user_id, workspace_id)
        if role not in {"owner", "admin"}:
            raise AuthorizationError("Workspace owner or admin access is required")
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
            {"user_id": user_id, "project_id": project_id},
        )
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Resource not found")
