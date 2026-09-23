from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import uuid6
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from shared.security.api_keys import (
    format_api_key_prefix,
    issue_control_api_key,
)
from shared.security.control_plane import (
    PROJECT_CONTROL_PERMISSIONS,
    WORKSPACE_CONTROL_PERMISSIONS,
    is_permission_subset,
    normalize_permissions,
)
from shared.security.principal import (
    AuthenticatedPrincipal,
    ControlPlanePrincipal,
    SecurityPrincipal,
)


class ControlKeyService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_keys(
        self,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            await self._require_workspace_permission(
                session,
                actor=actor,
                workspace_id=workspace_id,
                permission="keys:read",
            )
            result = await session.execute(
                text(
                    """
                    SELECT DISTINCT ON (credential_id)
                           id, credential_id, workspace_id, name, description,
                           key_prefix, key_version, permissions, status,
                           last_used_at, expires_at, revoked_at, rotated_from_id,
                           created_at, updated_at
                    FROM core.workspace_control_keys
                    WHERE workspace_id = :workspace_id
                    ORDER BY credential_id, created_at DESC, id DESC
                    """
                ),
                {"workspace_id": workspace_id},
            )
            rows = list(result.mappings().all())
            output: list[dict[str, Any]] = []
            for row in rows:
                grants = await self._grants_for_key(session, UUID(str(row["id"])))
                output.append(self._key_payload(row, grants=grants))
            return output

    async def create_key(
        self,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        name: str,
        description: str | None,
        permissions: list[str],
        project_grants: list[dict[str, Any]],
        expires_at: datetime | None,
    ) -> dict[str, Any]:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValidationError("Control key name cannot be blank")
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= datetime.now(UTC):
                raise ValidationError("Control key expiration must be in the future")

        workspace_permissions = self._normalize_workspace_permissions(permissions)
        normalized_grants = self._normalize_project_grants(project_grants)

        async with self._session_factory() as session:
            await self._require_workspace_permission(
                session,
                actor=actor,
                workspace_id=workspace_id,
                permission="keys:create",
            )
            await self._validate_projects_in_workspace(
                session,
                workspace_id=workspace_id,
                grants=normalized_grants,
            )
            await self._validate_delegation(
                session,
                actor=actor,
                workspace_id=workspace_id,
                workspace_permissions=workspace_permissions,
                grants=normalized_grants,
            )

            issued = issue_control_api_key()
            key_id = uuid6.uuid7()
            creator_user_id, creator_key_id = self._creator_ids(actor)
            now = datetime.now(UTC)
            await session.execute(
                text(
                    """
                    INSERT INTO core.workspace_control_keys
                        (id, workspace_id, credential_id, name, description,
                         key_prefix, key_hash, key_version, permissions, status,
                         expires_at, created_by_user_id, created_by_control_key_id,
                         created_at, updated_at)
                    VALUES
                        (:id, :workspace_id, :credential_id, :name, :description,
                         :key_prefix, :key_hash, :key_version, CAST(:permissions AS jsonb),
                         'active', :expires_at, :created_by_user_id,
                         :created_by_control_key_id, :now, :now)
                    """
                ),
                {
                    "id": key_id,
                    "workspace_id": workspace_id,
                    "credential_id": key_id,
                    "name": normalized_name,
                    "description": description.strip() if description else None,
                    "key_prefix": issued.public_prefix,
                    "key_hash": issued.digest,
                    "key_version": issued.key_version,
                    "permissions": self._json_array(workspace_permissions),
                    "expires_at": expires_at,
                    "created_by_user_id": creator_user_id,
                    "created_by_control_key_id": creator_key_id,
                    "now": now,
                },
            )
            await self._replace_grants(
                session,
                control_key_id=key_id,
                grants=normalized_grants,
                now=now,
            )
            await session.commit()

            return {
                "id": key_id,
                "credential_id": key_id,
                "workspace_id": workspace_id,
                "name": normalized_name,
                "description": description.strip() if description else None,
                "key": issued.value,
                "key_prefix": issued.display_prefix,
                "permissions": workspace_permissions,
                "project_grants": normalized_grants,
                "status": "active",
                "expires_at": expires_at,
                "created_at": now,
            }

    async def update_key(
        self,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        control_key_id: UUID,
        name: str | None,
        description: str | None,
        permissions: list[str] | None,
        project_grants: list[dict[str, Any]] | None,
        expires_at: datetime | None,
        expires_at_supplied: bool,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            await self._require_workspace_permission(
                session,
                actor=actor,
                workspace_id=workspace_id,
                permission="keys:update",
            )
            target = await self._target_row(
                session,
                workspace_id=workspace_id,
                control_key_id=control_key_id,
                require_active=True,
            )
            existing_grants = await self._grants_for_key(session, control_key_id)
            await self._assert_target_manageable(
                session,
                actor=actor,
                workspace_id=workspace_id,
                target=target,
                target_grants=existing_grants,
            )

            next_permissions = (
                self._normalize_workspace_permissions(permissions)
                if permissions is not None
                else list(target["permissions"] or [])
            )
            next_grants = (
                self._normalize_project_grants(project_grants)
                if project_grants is not None
                else existing_grants
            )
            await self._validate_projects_in_workspace(
                session,
                workspace_id=workspace_id,
                grants=next_grants,
            )
            await self._validate_delegation(
                session,
                actor=actor,
                workspace_id=workspace_id,
                workspace_permissions=next_permissions,
                grants=next_grants,
            )

            next_name = target["name"]
            if name is not None:
                next_name = name.strip()
                if not next_name:
                    raise ValidationError("Control key name cannot be blank")
            next_description = target["description"]
            if description is not None:
                next_description = description.strip() or None
            next_expires_at = target["expires_at"]
            if expires_at_supplied:
                next_expires_at = expires_at
                if next_expires_at is not None:
                    if next_expires_at.tzinfo is None:
                        next_expires_at = next_expires_at.replace(tzinfo=UTC)
                    if next_expires_at <= datetime.now(UTC):
                        raise ValidationError(
                            "Control key expiration must be in the future"
                        )

            now = datetime.now(UTC)
            await session.execute(
                text(
                    """
                    UPDATE core.workspace_control_keys
                    SET name = :name,
                        description = :description,
                        permissions = CAST(:permissions AS jsonb),
                        expires_at = :expires_at,
                        updated_at = :now
                    WHERE id = :id
                    """
                ),
                {
                    "id": control_key_id,
                    "name": next_name,
                    "description": next_description,
                    "permissions": self._json_array(next_permissions),
                    "expires_at": next_expires_at,
                    "now": now,
                },
            )
            if project_grants is not None:
                await self._replace_grants(
                    session,
                    control_key_id=control_key_id,
                    grants=next_grants,
                    now=now,
                )
            await session.commit()
            updated = dict(target)
            updated.update(
                {
                    "name": next_name,
                    "description": next_description,
                    "permissions": next_permissions,
                    "expires_at": next_expires_at,
                    "updated_at": now,
                }
            )
            return self._key_payload(updated, grants=next_grants)

    async def revoke_key(
        self,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        control_key_id: UUID,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            await self._require_workspace_permission(
                session,
                actor=actor,
                workspace_id=workspace_id,
                permission="keys:revoke",
            )
            target = await self._target_row(
                session,
                workspace_id=workspace_id,
                control_key_id=control_key_id,
                require_active=False,
            )
            target_grants = await self._grants_for_key(session, control_key_id)
            await self._assert_target_manageable(
                session,
                actor=actor,
                workspace_id=workspace_id,
                target=target,
                target_grants=target_grants,
            )
            now = datetime.now(UTC)
            await session.execute(
                text(
                    """
                    UPDATE core.workspace_control_keys
                    SET status = 'revoked',
                        revoked_at = COALESCE(revoked_at, :now),
                        updated_at = :now
                    WHERE id = :id
                    """
                ),
                {"id": control_key_id, "now": now},
            )
            await session.commit()
            return {
                "id": control_key_id,
                "workspace_id": workspace_id,
                "status": "revoked",
                "revoked_at": target["revoked_at"] or now,
            }

    async def rotate_key(
        self,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        control_key_id: UUID,
        name: str | None = None,
        expires_at: datetime | None = None,
        expires_at_supplied: bool = False,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            await self._require_workspace_permission(
                session,
                actor=actor,
                workspace_id=workspace_id,
                permission="keys:rotate",
            )
            target = await self._target_row(
                session,
                workspace_id=workspace_id,
                control_key_id=control_key_id,
                require_active=True,
            )
            grants = await self._grants_for_key(session, control_key_id)
            await self._assert_target_manageable(
                session,
                actor=actor,
                workspace_id=workspace_id,
                target=target,
                target_grants=grants,
            )

            next_name = target["name"] if name is None else name.strip()
            if not next_name:
                raise ValidationError("Control key name cannot be blank")
            next_expires_at = target["expires_at"]
            if expires_at_supplied:
                next_expires_at = expires_at
            if next_expires_at is not None:
                if next_expires_at.tzinfo is None:
                    next_expires_at = next_expires_at.replace(tzinfo=UTC)
                if next_expires_at <= datetime.now(UTC):
                    raise ValidationError("Control key expiration must be in the future")

            issued = issue_control_api_key()
            replacement_id = uuid6.uuid7()
            creator_user_id, creator_key_id = self._creator_ids(actor)
            now = datetime.now(UTC)

            await session.execute(
                text(
                    """
                    UPDATE core.workspace_control_keys
                    SET status = 'revoked',
                        revoked_at = :now,
                        updated_at = :now
                    WHERE id = :id
                    """
                ),
                {"id": control_key_id, "now": now},
            )
            await session.execute(
                text(
                    """
                    INSERT INTO core.workspace_control_keys
                        (id, workspace_id, credential_id, name, description,
                         key_prefix, key_hash, key_version, permissions, status,
                         expires_at, created_by_user_id, created_by_control_key_id,
                         rotated_from_id, created_at, updated_at)
                    VALUES
                        (:id, :workspace_id, :credential_id, :name, :description,
                         :key_prefix, :key_hash, :key_version, CAST(:permissions AS jsonb),
                         'active', :expires_at, :created_by_user_id,
                         :created_by_control_key_id, :rotated_from_id, :now, :now)
                    """
                ),
                {
                    "id": replacement_id,
                    "workspace_id": workspace_id,
                    "credential_id": target["credential_id"],
                    "name": next_name,
                    "description": target["description"],
                    "key_prefix": issued.public_prefix,
                    "key_hash": issued.digest,
                    "key_version": issued.key_version,
                    "permissions": self._json_array(list(target["permissions"] or [])),
                    "expires_at": next_expires_at,
                    "created_by_user_id": creator_user_id,
                    "created_by_control_key_id": creator_key_id,
                    "rotated_from_id": control_key_id,
                    "now": now,
                },
            )
            await self._replace_grants(
                session,
                control_key_id=replacement_id,
                grants=grants,
                now=now,
            )
            await session.commit()
            return {
                "id": replacement_id,
                "credential_id": target["credential_id"],
                "workspace_id": workspace_id,
                "name": next_name,
                "description": target["description"],
                "key": issued.value,
                "key_prefix": issued.display_prefix,
                "permissions": list(target["permissions"] or []),
                "project_grants": grants,
                "status": "active",
                "expires_at": next_expires_at,
                "created_at": now,
                "rotated_from_id": control_key_id,
            }

    async def list_accessible_projects(
        self,
        *,
        principal: ControlPlanePrincipal,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT p.id, p.workspace_id, p.name, p.slug, p.status,
                           p.created_at, p.updated_at,
                           g.permissions
                    FROM core.workspace_control_key_project_grants AS g
                    JOIN core.projects AS p ON p.id = g.project_id
                    WHERE g.control_key_id = :control_key_id
                      AND p.workspace_id = :workspace_id
                    ORDER BY p.created_at DESC
                    """
                ),
                {
                    "control_key_id": principal.api_key_id,
                    "workspace_id": principal.workspace_id,
                },
            )
            return [dict(row) for row in result.mappings().all()]

    async def _require_workspace_permission(
        self,
        session: AsyncSession,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        permission: str,
    ) -> None:
        if isinstance(actor, AuthenticatedPrincipal):
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
                {"user_id": actor.user_id, "workspace_id": workspace_id},
            )
            role = result.scalar_one_or_none()
            if role not in {"owner", "admin"}:
                raise AuthorizationError(
                    "Workspace owner or admin access is required"
                )
            return

        if isinstance(actor, ControlPlanePrincipal):
            if actor.workspace_id != workspace_id:
                raise NotFoundError("Resource not found")
            if permission not in actor.permissions:
                raise AuthorizationError("Control key permission is not sufficient")
            return

        raise AuthorizationError("Authentication required")

    async def _validate_delegation(
        self,
        session: AsyncSession,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        workspace_permissions: list[str],
        grants: list[dict[str, Any]],
    ) -> None:
        if isinstance(actor, AuthenticatedPrincipal):
            return
        if not isinstance(actor, ControlPlanePrincipal):
            raise AuthorizationError("Authentication required")
        if actor.workspace_id != workspace_id:
            raise NotFoundError("Resource not found")
        if not is_permission_subset(
            set(workspace_permissions),
            set(actor.permissions),
        ):
            raise AuthorizationError(
                "A control key cannot delegate Workspace permissions it does not own"
            )
        actor_grants = {
            item["project_id"]: set(item["permissions"])
            for item in await self._grants_for_key(session, actor.api_key_id)
        }
        for grant in grants:
            project_id = grant["project_id"]
            available = actor_grants.get(project_id)
            if available is None:
                raise AuthorizationError(
                    "A control key cannot delegate access to an ungranted Project"
                )
            if not is_permission_subset(set(grant["permissions"]), available):
                raise AuthorizationError(
                    "A control key cannot delegate Project permissions it does not own"
                )

    async def _assert_target_manageable(
        self,
        session: AsyncSession,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        target: dict[str, Any],
        target_grants: list[dict[str, Any]],
    ) -> None:
        if isinstance(actor, AuthenticatedPrincipal):
            return
        if not isinstance(actor, ControlPlanePrincipal):
            raise AuthorizationError("Authentication required")
        if actor.workspace_id != workspace_id:
            raise NotFoundError("Resource not found")
        if UUID(str(target["credential_id"])) == actor.credential_id:
            raise AuthorizationError("A control key cannot alter its own credential")
        if not is_permission_subset(
            set(str(item) for item in (target["permissions"] or [])),
            set(actor.permissions),
        ):
            raise AuthorizationError(
                "A control key cannot manage a key with broader Workspace permissions"
            )
        actor_grants = {
            item["project_id"]: set(item["permissions"])
            for item in await self._grants_for_key(session, actor.api_key_id)
        }
        for grant in target_grants:
            available = actor_grants.get(grant["project_id"])
            if available is None or not is_permission_subset(
                set(grant["permissions"]),
                available,
            ):
                raise AuthorizationError(
                    "A control key cannot manage a key with broader Project access"
                )

    async def _target_row(
        self,
        session: AsyncSession,
        *,
        workspace_id: UUID,
        control_key_id: UUID,
        require_active: bool,
    ) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                SELECT id, credential_id, workspace_id, name, description,
                       key_prefix, key_version, permissions, status,
                       last_used_at, expires_at, revoked_at, rotated_from_id,
                       created_at, updated_at
                FROM core.workspace_control_keys
                WHERE id = :id AND workspace_id = :workspace_id
                """
            ),
            {"id": control_key_id, "workspace_id": workspace_id},
        )
        row = result.mappings().first()
        if row is None:
            raise NotFoundError("Control key not found")
        data = dict(row)
        if require_active and (
            data["status"] != "active" or data["revoked_at"] is not None
        ):
            raise ConflictError("Only active control keys can be changed")
        return data

    async def _grants_for_key(
        self,
        session: AsyncSession,
        control_key_id: UUID,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT project_id, permissions
                FROM core.workspace_control_key_project_grants
                WHERE control_key_id = :control_key_id
                ORDER BY project_id
                """
            ),
            {"control_key_id": control_key_id},
        )
        return [
            {
                "project_id": UUID(str(row["project_id"])),
                "permissions": [str(item) for item in (row["permissions"] or [])],
            }
            for row in result.mappings().all()
        ]

    async def _replace_grants(
        self,
        session: AsyncSession,
        *,
        control_key_id: UUID,
        grants: list[dict[str, Any]],
        now: datetime,
    ) -> None:
        await session.execute(
            text(
                """
                DELETE FROM core.workspace_control_key_project_grants
                WHERE control_key_id = :control_key_id
                """
            ),
            {"control_key_id": control_key_id},
        )
        for grant in grants:
            await session.execute(
                text(
                    """
                    INSERT INTO core.workspace_control_key_project_grants
                        (id, control_key_id, project_id, permissions, created_at, updated_at)
                    VALUES
                        (:id, :control_key_id, :project_id,
                         CAST(:permissions AS jsonb), :now, :now)
                    """
                ),
                {
                    "id": uuid6.uuid7(),
                    "control_key_id": control_key_id,
                    "project_id": grant["project_id"],
                    "permissions": self._json_array(grant["permissions"]),
                    "now": now,
                },
            )

    async def _validate_projects_in_workspace(
        self,
        session: AsyncSession,
        *,
        workspace_id: UUID,
        grants: list[dict[str, Any]],
    ) -> None:
        for grant in grants:
            result = await session.execute(
                text(
                    """
                    SELECT 1
                    FROM core.projects
                    WHERE id = :project_id
                      AND workspace_id = :workspace_id
                    """
                ),
                {
                    "project_id": grant["project_id"],
                    "workspace_id": workspace_id,
                },
            )
            if result.scalar_one_or_none() is None:
                raise NotFoundError("Project not found")

    def _normalize_workspace_permissions(self, permissions: list[str]) -> list[str]:
        try:
            return normalize_permissions(
                permissions,
                allowed=WORKSPACE_CONTROL_PERMISSIONS,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def _normalize_project_grants(
        self,
        project_grants: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        seen_projects: set[UUID] = set()
        for item in project_grants:
            try:
                project_id = UUID(str(item["project_id"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValidationError("Invalid Project grant project_id") from exc
            if project_id in seen_projects:
                raise ValidationError("Project grants must be unique per Project")
            seen_projects.add(project_id)
            try:
                permissions = normalize_permissions(
                    list(item.get("permissions") or []),
                    allowed=PROJECT_CONTROL_PERMISSIONS,
                )
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
            if not permissions:
                raise ValidationError(
                    "Each Project grant requires at least one permission"
                )
            normalized.append(
                {"project_id": project_id, "permissions": permissions}
            )
        return normalized

    @staticmethod
    def _creator_ids(
        actor: SecurityPrincipal,
    ) -> tuple[UUID | None, UUID | None]:
        if isinstance(actor, AuthenticatedPrincipal):
            return actor.user_id, None
        if isinstance(actor, ControlPlanePrincipal):
            return None, actor.api_key_id
        return None, None

    @staticmethod
    def _json_array(values: list[str]) -> str:
        import json

        return json.dumps(values, separators=(",", ":"))

    @staticmethod
    def _key_payload(
        row: dict[str, Any],
        *,
        grants: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "id": UUID(str(row["id"])),
            "credential_id": UUID(str(row["credential_id"])),
            "workspace_id": UUID(str(row["workspace_id"])),
            "name": row["name"],
            "description": row["description"],
            "key_prefix": format_api_key_prefix(
                str(row["key_prefix"]),
                key_version=int(row["key_version"]),
                kind="control",
                environment=None,
            ),
            "permissions": [str(item) for item in (row["permissions"] or [])],
            "project_grants": grants,
            "status": row["status"],
            "last_used_at": row.get("last_used_at"),
            "expires_at": row.get("expires_at"),
            "revoked_at": row.get("revoked_at"),
            "rotated_from_id": row.get("rotated_from_id"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
