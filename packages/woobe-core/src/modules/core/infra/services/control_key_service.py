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
    normalize_conditions,
    conditions_are_subset,
    require_expiration_ceiling,
)
from shared.security.authority import CategoryResolver
from shared.security.tenancy import TenantAuthorizer
from shared.contracts.errors import PreconditionFailedError
from shared.security.principal import (
    AuthenticatedPrincipal,
    ControlPlanePrincipal,
    SecurityPrincipal,
)


class ControlKeyService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        category_resolver: CategoryResolver | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._category_resolver = category_resolver

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
                       delegation_expires_at, on_project_create_permissions, revision,
                       workspace_category_id, workspace_category_revision,
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
        on_project_create_permissions: list[str] | None = None,
        category_id: UUID | None = None,
        category_revision: int | None = None,
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
        ceiling = self._expiration_ceiling(actor)
        self._check_expiration(expires_at, ceiling)
        creation_permissions = self._creation_permissions(
            actor, on_project_create_permissions
        )

        async with self._session_factory() as session:
            await self._require_workspace_permission(
                session,
                actor=actor,
                workspace_id=workspace_id,
                permission="keys:create",
            )
            workspace_permissions, category_revision = await self._workspace_category(
                session,
                workspace_id,
                workspace_permissions,
                category_id,
                category_revision,
            )
            normalized_grants = await self._materialize_grants(
                session, workspace_id, project_grants
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
                         expires_at, delegation_expires_at, on_project_create_permissions,
                         workspace_category_id, workspace_category_revision,
                         created_by_user_id, created_by_control_key_id,
                         created_at, updated_at)
                    VALUES
                        (:id, :workspace_id, :credential_id, :name, :description,
                         :key_prefix, :key_hash, :key_version, CAST(:permissions AS jsonb),
                         'active', :expires_at, :delegation_expires_at, CAST(:creation_permissions AS jsonb),
                         :category_id, :category_revision, :created_by_user_id,
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
                    "delegation_expires_at": ceiling,
                    "creation_permissions": self._json_array(creation_permissions),
                    "category_id": category_id,
                    "category_revision": category_revision,
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
                "delegation_expires_at": ceiling,
                "on_project_create_permissions": creation_permissions,
                "category_id": category_id,
                "category_revision": category_revision,
                "revision": 1,
                "etag": f'"control-key:{key_id}:1"',
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
        description_supplied: bool,
        permissions: list[str] | None,
        project_grants: list[dict[str, Any]] | None,
        expires_at: datetime | None,
        expires_at_supplied: bool,
        expected_revision: int | None = None,
        on_project_create_permissions: list[str] | None = None,
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
            self._require_revision(target, expected_revision)
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
                await self._materialize_grants(session, workspace_id, project_grants)
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
            if description_supplied:
                next_description = description.strip() if description else None
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
            self._check_expiration(
                next_expires_at,
                self._expiration_ceiling(actor, target.get("delegation_expires_at")),
            )
            creation_permissions = (
                list(target.get("on_project_create_permissions") or [])
                if on_project_create_permissions is None
                else self._creation_permissions(actor, on_project_create_permissions)
            )
            await session.execute(
                text(
                    """
                    UPDATE core.workspace_control_keys
                    SET name = :name,
                        description = :description,
                        permissions = CAST(:permissions AS jsonb),
                        expires_at = :expires_at,
                        on_project_create_permissions = CAST(:creation_permissions AS jsonb),
                        revision = revision + 1,
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
                    "creation_permissions": self._json_array(creation_permissions),
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
                    "revision": int(target.get("revision", 1)) + 1,
                    "on_project_create_permissions": creation_permissions,
                }
            )
            return self._key_payload(updated, grants=next_grants)

    async def revoke_key(
        self,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        control_key_id: UUID,
        expected_revision: int | None = None,
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
            self._require_revision(target, expected_revision)
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
                        revision = revision + 1,
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
                "revision": int(target.get("revision", 1)) + 1,
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
        expected_revision: int | None = None,
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
            self._require_revision(target, expected_revision)
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
                    raise ValidationError(
                        "Control key expiration must be in the future"
                    )

            self._check_expiration(
                next_expires_at,
                self._expiration_ceiling(actor, target.get("delegation_expires_at")),
            )
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
                        revision = revision + 1,
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
                         expires_at, delegation_expires_at, on_project_create_permissions,
                         workspace_category_id, workspace_category_revision, revision,
                         created_by_user_id, created_by_control_key_id,
                         rotated_from_id, created_at, updated_at)
                    VALUES
                        (:id, :workspace_id, :credential_id, :name, :description,
                         :key_prefix, :key_hash, :key_version, CAST(:permissions AS jsonb),
                         'active', :expires_at, :delegation_expires_at, CAST(:creation_permissions AS jsonb),
                         :category_id, :category_revision, :revision, :created_by_user_id,
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
                    "delegation_expires_at": target.get("delegation_expires_at"),
                    "creation_permissions": self._json_array(
                        list(target.get("on_project_create_permissions") or [])
                    ),
                    "category_id": target.get("workspace_category_id"),
                    "category_revision": target.get("workspace_category_revision"),
                    "revision": int(target.get("revision", 1)) + 1,
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
                "delegation_expires_at": target.get("delegation_expires_at"),
                "on_project_create_permissions": list(
                    target.get("on_project_create_permissions") or []
                ),
                "revision": int(target.get("revision", 1)) + 1,
                "etag": f'"control-key:{replacement_id}:{int(target.get("revision", 1)) + 1}"',
            }

    async def create_project_atomically(
        self, *, principal: ControlPlanePrincipal, payload: dict[str, Any]
    ) -> dict[str, Any]:
        from modules.core.application.dtos.create_project_dtos import CreateProjectInput
        from modules.core.application.use_cases.create_project_use_case import (
            CreateProjectUseCase,
        )
        from modules.core.infra.database.repositories import (
            SQLAlchemyProjectRepository,
            SQLAlchemyOutboxEventWriter,
        )

        input_dto = CreateProjectInput.model_validate(payload)
        async with self._session_factory() as session:
            await self._require_workspace_permission(
                session,
                actor=principal,
                workspace_id=input_dto.workspace_id,
                permission="projects:create",
            )
            use_case = CreateProjectUseCase(
                SQLAlchemyProjectRepository(session),
                SQLAlchemyOutboxEventWriter(session),
            )
            project = await use_case.execute(input_dto)
            await self._grant_created_project(
                session, principal=principal, project_id=project.id
            )
            await session.commit()
            return project.model_dump(mode="json")

    async def grant_created_project(
        self, *, principal: ControlPlanePrincipal, project_id: UUID
    ) -> None:
        async with self._session_factory() as session:
            await self._grant_created_project(
                session, principal=principal, project_id=project_id
            )
            await session.commit()

    async def _grant_created_project(
        self,
        session: AsyncSession,
        *,
        principal: ControlPlanePrincipal,
        project_id: UUID,
    ) -> None:
        await self._require_workspace_permission(
            session,
            actor=principal,
            workspace_id=principal.workspace_id,
            permission="projects:create",
        )
        result = await session.execute(
            text(
                """
                SELECT workspace_id
                FROM core.projects
                WHERE id = :project_id
                """
            ),
            {"project_id": project_id},
        )
        workspace_id = result.scalar_one_or_none()
        if workspace_id is None or UUID(str(workspace_id)) != principal.workspace_id:
            raise NotFoundError("Project not found")

        now = datetime.now(UTC)
        await session.execute(
            text(
                """
                INSERT INTO core.workspace_control_key_project_grants
                    (id, control_key_id, project_id, permissions, created_at, updated_at)
                VALUES
                    (:id, :control_key_id, :project_id,
                     CAST(:permissions AS jsonb), :now, :now)
                ON CONFLICT (control_key_id, project_id)
                DO UPDATE SET
                    permissions = EXCLUDED.permissions,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": uuid6.uuid7(),
                "control_key_id": principal.api_key_id,
                "project_id": project_id,
                "permissions": self._json_array(
                    sorted(principal.on_project_create_permissions)
                ),
                "now": now,
            },
        )

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
                raise AuthorizationError("Workspace owner or admin access is required")
            await TenantAuthorizer(session).require_human_permission(
                user_id=actor.user_id,
                workspace_id=workspace_id,
                project_id=None,
                permission=permission,
            )
            return

        if isinstance(actor, ControlPlanePrincipal):
            await TenantAuthorizer(session).require_active_control(actor)
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
            authorizer = TenantAuthorizer(session)
            for permission in workspace_permissions:
                await authorizer.require_human_permission(
                    user_id=actor.user_id,
                    workspace_id=workspace_id,
                    project_id=None,
                    permission=permission,
                )
            for grant in grants:
                for permission in grant["permissions"]:
                    await authorizer.require_human_permission(
                        user_id=actor.user_id,
                        workspace_id=workspace_id,
                        project_id=grant["project_id"],
                        permission=permission,
                    )
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
            actor_conditions = next(
                (
                    item.get("conditions", {})
                    for item in await self._grants_for_key(session, actor.api_key_id)
                    if item["project_id"] == project_id
                ),
                {},
            )
            if not conditions_are_subset(grant.get("conditions", {}), actor_conditions):
                raise AuthorizationError(
                    "A control key cannot broaden grant conditions"
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
            await self._validate_delegation(
                session,
                actor=actor,
                workspace_id=workspace_id,
                workspace_permissions=list(target["permissions"] or []),
                grants=target_grants,
            )
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
        if (
            not set(target.get("on_project_create_permissions") or [])
            <= actor.on_project_create_permissions
        ):
            raise AuthorizationError(
                "A control key cannot manage broader Project creation authority"
            )
        actor_condition_map = {
            item["project_id"]: item.get("conditions", {})
            for item in await self._grants_for_key(session, actor.api_key_id)
        }
        for grant in target_grants:
            if not conditions_are_subset(
                grant.get("conditions", {}),
                actor_condition_map.get(grant["project_id"], {}),
            ):
                raise AuthorizationError(
                    "A control key cannot manage broader grant conditions"
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
                       delegation_expires_at, on_project_create_permissions, revision,
                       workspace_category_id, workspace_category_revision,
                       created_at, updated_at
                FROM core.workspace_control_keys
                WHERE id = :id AND workspace_id = :workspace_id
                FOR UPDATE
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
                SELECT project_id, permissions, conditions, category_id, category_revision
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
                "conditions": dict(row.get("conditions") or {}),
                "category_id": row.get("category_id"),
                "category_revision": row.get("category_revision"),
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
                        (id, control_key_id, project_id, permissions, conditions, category_id, category_revision, created_at, updated_at)
                    VALUES
                        (:id, :control_key_id, :project_id,
                         CAST(:permissions AS jsonb), CAST(:conditions AS jsonb), :category_id, :category_revision, :now, :now)
                    """
                ),
                {
                    "id": uuid6.uuid7(),
                    "control_key_id": control_key_id,
                    "project_id": grant["project_id"],
                    "permissions": self._json_array(grant["permissions"]),
                    "conditions": self._json_object(grant.get("conditions", {})),
                    "category_id": grant.get("category_id"),
                    "category_revision": grant.get("category_revision"),
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
                {
                    "project_id": project_id,
                    "permissions": permissions,
                    "conditions": normalize_conditions(item.get("conditions")),
                    "category_id": item.get("category_id"),
                    "category_revision": item.get("category_revision"),
                }
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
    def _expiration_ceiling(
        actor: SecurityPrincipal, target_ceiling: datetime | None = None
    ) -> datetime | None:
        values = [target_ceiling]
        if isinstance(actor, ControlPlanePrincipal):
            values.extend([actor.expires_at, actor.delegation_expires_at])
        return (
            min(value for value in values if value is not None)
            if any(value is not None for value in values)
            else None
        )

    @staticmethod
    def _check_expiration(
        expires_at: datetime | None, ceiling: datetime | None
    ) -> None:
        try:
            require_expiration_ceiling(expires_at, ceiling)
        except ValueError as exc:
            raise AuthorizationError(str(exc)) from exc

    @staticmethod
    def _require_revision(
        target: dict[str, Any], expected_revision: int | None
    ) -> None:
        if expected_revision is None:
            raise ValidationError("An expected revision is required")
        if expected_revision != int(target.get("revision", 1)):
            raise PreconditionFailedError("Control key revision has changed")

    def _creation_permissions(
        self, actor: SecurityPrincipal, requested: list[str] | None
    ) -> list[str]:
        if requested is None:
            return (
                sorted(actor.on_project_create_permissions)
                if isinstance(actor, ControlPlanePrincipal)
                else ["project:read"]
            )
        try:
            result = normalize_permissions(
                requested, allowed=PROJECT_CONTROL_PERMISSIONS
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        if (
            isinstance(actor, ControlPlanePrincipal)
            and not set(result) <= actor.on_project_create_permissions
        ):
            raise AuthorizationError(
                "Project creation permissions exceed the delegation ceiling"
            )
        return result

    async def _workspace_category(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        permissions: list[str],
        category_id: UUID | None,
        revision: int | None,
    ) -> tuple[list[str], int | None]:
        if category_id is None:
            if revision is not None:
                raise ValidationError("category_revision requires category_id")
            return permissions, None
        if self._category_resolver is None:
            raise ValidationError("Category resolution is unavailable")
        category = await self._category_resolver.resolve_category(
            workspace_id=workspace_id,
            category_id=category_id,
            revision=revision,
            scope="workspace",
            transaction=session,
        )
        return sorted(set(permissions) | set(category["permissions"])), category[
            "revision"
        ]

    async def _materialize_grants(
        self, session: AsyncSession, workspace_id: UUID, grants: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        output = []
        for raw in grants:
            item = dict(raw)
            if item.get("category_id") is not None:
                if self._category_resolver is None:
                    raise ValidationError("Category resolution is unavailable")
                category = await self._category_resolver.resolve_category(
                    workspace_id=workspace_id,
                    category_id=UUID(str(item["category_id"])),
                    revision=item.get("category_revision"),
                    scope="project",
                    transaction=session,
                )
                requested = (
                    normalize_conditions(item.get("conditions"))
                    if item.get("conditions") is not None
                    else category["conditions"]
                )
                if not conditions_are_subset(requested, category["conditions"]):
                    raise AuthorizationError("Category conditions cannot be broadened")
                item.update(
                    permissions=sorted(
                        set(item.get("permissions") or [])
                        | set(category["permissions"])
                    ),
                    conditions=requested,
                    category_id=category["id"],
                    category_revision=category["revision"],
                )
            elif item.get("category_revision") is not None:
                raise ValidationError("category_revision requires category_id")
            output.append(item)
        try:
            return self._normalize_project_grants(output)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    @staticmethod
    def _json_object(value: dict[str, Any]) -> str:
        import json

        return json.dumps(value, separators=(",", ":"))

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
            "revision": int(row.get("revision", 1)),
            "etag": f'"control-key:{row["id"]}:{int(row.get("revision", 1))}"',
            "delegation_expires_at": row.get("delegation_expires_at"),
            "on_project_create_permissions": list(
                row.get("on_project_create_permissions") or []
            ),
            "category_id": row.get("workspace_category_id"),
            "category_revision": row.get("workspace_category_revision"),
        }
