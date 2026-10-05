from __future__ import annotations

import re
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Uuid, bindparam, delete, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.database.authority_models import (
    AuthorityAssignmentModel,
    AuthorityAuditModel,
    AuthorityCategoryModel,
    AuthorityCategoryVersionModel,
)
from shared.contracts.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    ValidationError,
)
from shared.security.control_plane import (
    CATALOG_REVISION,
    PROJECT_CONTROL_PERMISSIONS,
    SELF_CONTROL_PERMISSIONS,
    WORKSPACE_CONTROL_PERMISSIONS,
    expand_permissions,
    normalize_conditions,
    system_profiles,
)
from shared.security.principal import (
    AuthenticatedPrincipal,
    ControlPlanePrincipal,
    SecurityPrincipal,
)
from shared.security.tenancy import TenantAuthorizer


class AuthorityService:
    """Workspace-owned, immutable permission revisions; grants copy their values."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def require_permission(
        self,
        session: AsyncSession,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        permission: str,
    ) -> None:
        if isinstance(actor, ControlPlanePrincipal):
            await TenantAuthorizer(session).require_active_control(actor)
            if actor.workspace_id != workspace_id:
                raise NotFoundError("Resource not found")
            if (
                permission not in actor.permissions
                and permission not in SELF_CONTROL_PERMISSIONS
            ):
                raise AuthorizationError("Control key permission is not sufficient")
            return
        if not isinstance(actor, AuthenticatedPrincipal):
            raise AuthorizationError("Administrative authentication required")
        authorizer = TenantAuthorizer(session)
        role = await authorizer._workspace_role(actor.user_id, workspace_id)
        if role is None:
            raise NotFoundError("Resource not found")
        if (
            permission in {"categories:read", "workspace:read"}
            or permission in SELF_CONTROL_PERMISSIONS
        ):
            return
        await authorizer.require_human_permission(
            user_id=actor.user_id,
            workspace_id=workspace_id,
            project_id=None,
            permission=permission,
        )

    @staticmethod
    def _profile_id(workspace_id: UUID, name: str) -> UUID:
        return uuid5(
            NAMESPACE_URL, f"woobe:{workspace_id}:authority:{CATALOG_REVISION}:{name}"
        )

    def _profile(self, workspace_id: UUID, category_id: UUID) -> dict[str, Any] | None:
        for name, (scope, permissions) in system_profiles().items():
            if self._profile_id(workspace_id, name) == category_id:
                return {
                    "id": category_id,
                    "workspace_id": workspace_id,
                    "name": name,
                    "scope": scope,
                    "description": None,
                    "revision": 1,
                    "permissions": sorted(permissions),
                    "conditions": {},
                    "catalog_revision": CATALOG_REVISION,
                    "system": True,
                    "status": "active",
                }
        return None

    async def _category(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        category_id: UUID,
        *,
        lock: bool = False,
    ) -> AuthorityCategoryModel | None:
        query = select(AuthorityCategoryModel).where(
            AuthorityCategoryModel.id == category_id,
            AuthorityCategoryModel.workspace_id == workspace_id,
        )
        if lock:
            query = query.with_for_update()
        return (await session.execute(query)).scalar_one_or_none()

    async def _version(
        self, session: AsyncSession, category_id: UUID, revision: int
    ) -> AuthorityCategoryVersionModel:
        version = (
            await session.execute(
                select(AuthorityCategoryVersionModel).where(
                    AuthorityCategoryVersionModel.category_id == category_id,
                    AuthorityCategoryVersionModel.revision == revision,
                )
            )
        ).scalar_one_or_none()
        if version is None:
            raise NotFoundError("Category revision not found")
        return version

    @staticmethod
    def _payload(
        category: AuthorityCategoryModel, version: AuthorityCategoryVersionModel
    ) -> dict[str, Any]:
        return {
            "id": category.id,
            "workspace_id": category.workspace_id,
            "name": category.name,
            "scope": category.scope,
            "description": version.description,
            "revision": version.revision,
            "permissions": list(version.permissions),
            "conditions": dict(version.conditions),
            "catalog_revision": version.catalog_revision,
            "system": category.system,
            "status": category.status,
            "created_at": version.created_at,
            "updated_at": category.updated_at,
        }

    def _audit(
        self,
        session: AsyncSession,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        operation: str,
        subject_id: UUID,
        revision: int,
        details: dict[str, Any],
    ) -> None:
        session.add(
            AuthorityAuditModel(
                workspace_id=workspace_id,
                actor_user_id=actor.user_id
                if isinstance(actor, AuthenticatedPrincipal)
                else None,
                actor_control_key_id=actor.api_key_id
                if isinstance(actor, ControlPlanePrincipal)
                else None,
                operation=operation,
                subject_id=subject_id,
                revision=revision,
                details=details,
            )
        )

    async def list_categories(
        self,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        limit: int = 100,
        cursor: UUID | None = None,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 200:
            raise ValidationError("limit must be between 1 and 200")
        async with self._session_factory() as session:
            await self.require_permission(
                session, actor, workspace_id, "categories:read"
            )
            query = select(AuthorityCategoryModel).where(
                AuthorityCategoryModel.workspace_id == workspace_id
            )
            if cursor is not None:
                query = query.where(AuthorityCategoryModel.id > cursor)
            rows = list(
                (
                    await session.execute(
                        query.order_by(AuthorityCategoryModel.id).limit(limit + 1)
                    )
                ).scalars()
            )
            items = [
                self._payload(c, await self._version(session, c.id, c.revision))
                for c in rows[:limit]
            ]
            profiles = [
                self._profile(workspace_id, self._profile_id(workspace_id, name))
                for name in system_profiles()
            ]
            present = {item["id"] for item in items}
            return {
                "items": items,
                "system_categories": [p for p in profiles if p["id"] not in present],
                "next_cursor": str(rows[limit - 1].id) if len(rows) > limit else None,
                "complete": len(rows) <= limit,
            }

    async def get_category(
        self,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        category_id: UUID,
        revision: int | None = None,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            await self.require_permission(
                session, actor, workspace_id, "categories:read"
            )
            category = await self._category(session, workspace_id, category_id)
            if category is None:
                profile = self._profile(workspace_id, category_id)
                if profile is None or revision not in {None, 1}:
                    raise NotFoundError("Category not found")
                return profile
            return self._payload(
                category,
                await self._version(
                    session, category.id, revision or category.revision
                ),
            )

    @staticmethod
    def _normalize(data: dict[str, Any]) -> tuple[str, list[str], dict[str, Any]]:
        name = data["name"].strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,127}", name):
            raise ValidationError(
                "Category name must be a bounded lowercase identifier"
            )
        try:
            permissions = expand_permissions(
                data["permissions"],
                scope=data["scope"],
                catalog_revision=data.get("catalog_revision"),
            )
            conditions = normalize_conditions(data.get("conditions"))
        except (ValueError, TypeError) as exc:
            raise ValidationError(str(exc)) from exc
        if data["scope"] == "workspace" and conditions:
            raise ValidationError("Target conditions belong to Project categories")
        return name, permissions, conditions

    async def create_category(
        self, *, actor: SecurityPrincipal, workspace_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any]:
        name, permissions, conditions = self._normalize(data)
        if name in system_profiles():
            raise ConflictError(
                "System category names are reserved; clone with another name"
            )
        async with self._session_factory() as session:
            await self.require_permission(
                session, actor, workspace_id, "categories:create"
            )
            category = AuthorityCategoryModel(
                workspace_id=workspace_id,
                name=name,
                description=data.get("description"),
                scope=data["scope"],
                revision=1,
                status="active",
                system=False,
            )
            session.add(category)
            try:
                await session.flush()
                version = AuthorityCategoryVersionModel(
                    category_id=category.id,
                    revision=1,
                    permissions=permissions,
                    conditions=conditions,
                    catalog_revision=CATALOG_REVISION,
                    description=category.description,
                    created_by_user_id=actor.user_id
                    if isinstance(actor, AuthenticatedPrincipal)
                    else None,
                    created_by_control_key_id=actor.api_key_id
                    if isinstance(actor, ControlPlanePrincipal)
                    else None,
                )
                session.add(version)
                self._audit(
                    session,
                    actor=actor,
                    workspace_id=workspace_id,
                    operation="category.create",
                    subject_id=category.id,
                    revision=1,
                    details={"permissions": permissions, "conditions": conditions},
                )
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ConflictError(
                    "Category name already exists in this scope"
                ) from exc
            return self._payload(category, version)

    async def update_category(
        self,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        category_id: UUID,
        expected_revision: int,
        changes: dict[str, Any],
        archive: bool = False,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            await self.require_permission(
                session,
                actor,
                workspace_id,
                "categories:archive" if archive else "categories:update",
            )
            category = await self._category(
                session, workspace_id, category_id, lock=True
            )
            if category is None:
                if self._profile(workspace_id, category_id):
                    raise ConflictError(
                        "System categories are immutable; clone instead"
                    )
                raise NotFoundError("Category not found")
            if category.system:
                raise ConflictError("System categories are immutable; clone instead")
            if category.revision != expected_revision:
                raise PreconditionFailedError("Category revision has changed")
            if category.status != "active":
                raise ConflictError("Archived categories cannot be changed")
            old = await self._version(session, category.id, category.revision)
            data = {
                "name": category.name,
                "scope": category.scope,
                "permissions": old.permissions,
                "conditions": old.conditions,
                "catalog_revision": CATALOG_REVISION,
                "description": old.description,
                **changes,
            }
            if data["scope"] != category.scope:
                raise ValidationError("Category scope is immutable")
            name, permissions, conditions = self._normalize(data)
            if name in system_profiles():
                raise ConflictError("System category names are reserved")
            next_revision = category.revision + 1
            result = await session.execute(
                update(AuthorityCategoryModel)
                .where(
                    AuthorityCategoryModel.id == category.id,
                    AuthorityCategoryModel.revision == expected_revision,
                )
                .values(
                    name=name,
                    description=data.get("description"),
                    revision=next_revision,
                    status="archived" if archive else "active",
                )
            )
            if result.rowcount != 1:
                raise PreconditionFailedError("Category revision has changed")
            version = AuthorityCategoryVersionModel(
                category_id=category.id,
                revision=next_revision,
                permissions=permissions,
                conditions=conditions,
                catalog_revision=CATALOG_REVISION,
                description=data.get("description"),
                created_by_user_id=actor.user_id
                if isinstance(actor, AuthenticatedPrincipal)
                else None,
                created_by_control_key_id=actor.api_key_id
                if isinstance(actor, ControlPlanePrincipal)
                else None,
            )
            session.add(version)
            self._audit(
                session,
                actor=actor,
                workspace_id=workspace_id,
                operation="category.archive" if archive else "category.update",
                subject_id=category.id,
                revision=next_revision,
                details={
                    "before_permissions": old.permissions,
                    "permissions": permissions,
                    "conditions": conditions,
                },
            )
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ConflictError(
                    "Category name already exists in this scope"
                ) from exc
            await session.refresh(category)
            return self._payload(category, version)

    async def category_history(
        self,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        category_id: UUID,
        limit: int = 100,
        before_revision: int | None = None,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 200:
            raise ValidationError("limit must be between 1 and 200")
        await self.get_category(
            actor=actor, workspace_id=workspace_id, category_id=category_id
        )
        async with self._session_factory() as session:
            category = await self._category(session, workspace_id, category_id)
            if category is None:
                return {
                    "items": [self._profile(workspace_id, category_id)],
                    "next_revision": None,
                    "complete": True,
                }
            query = select(AuthorityCategoryVersionModel).where(
                AuthorityCategoryVersionModel.category_id == category_id
            )
            if before_revision is not None:
                query = query.where(
                    AuthorityCategoryVersionModel.revision < before_revision
                )
            versions = list(
                (
                    await session.execute(
                        query.order_by(
                            AuthorityCategoryVersionModel.revision.desc()
                        ).limit(limit + 1)
                    )
                ).scalars()
            )
            return {
                "items": [self._payload(category, v) for v in versions[:limit]],
                "next_revision": versions[limit - 1].revision
                if len(versions) > limit
                else None,
                "complete": len(versions) <= limit,
            }

    async def delete_category(
        self,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        category_id: UUID,
        expected_revision: int,
    ) -> None:
        async with self._session_factory() as session:
            await self.require_permission(
                session, actor, workspace_id, "categories:delete"
            )
            category = await self._category(
                session, workspace_id, category_id, lock=True
            )
            if category is None or category.system:
                raise ConflictError(
                    "Only unused archived custom categories can be deleted"
                )
            if category.revision != expected_revision:
                raise PreconditionFailedError("Category revision has changed")
            if category.status != "archived":
                raise ConflictError("Archive the category before deletion")
            self._audit(
                session,
                actor=actor,
                workspace_id=workspace_id,
                operation="category.delete",
                subject_id=category_id,
                revision=category.revision,
                details={},
            )
            try:
                await session.execute(
                    delete(AuthorityCategoryModel).where(
                        AuthorityCategoryModel.id == category_id
                    )
                )
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ConflictError(
                    "Category revisions are referenced by grants or assignments"
                ) from exc

    async def resolve_category(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        revision: int | None,
        scope: str,
        transaction: object,
    ) -> dict[str, Any]:
        if not isinstance(transaction, AsyncSession):
            raise TypeError("Category resolution requires the grant transaction")
        session = transaction
        category = await self._category(session, workspace_id, category_id, lock=True)
        if category is None:
            profile = self._profile(workspace_id, category_id)
            if (
                profile is None
                or revision not in {None, 1}
                or profile["scope"] != scope
            ):
                raise NotFoundError("Category not found")
            category = AuthorityCategoryModel(
                id=category_id,
                workspace_id=workspace_id,
                name=profile["name"],
                scope=scope,
                revision=1,
                system=True,
                status="active",
            )
            session.add(category)
            await session.flush()
            version = AuthorityCategoryVersionModel(
                category_id=category_id,
                revision=1,
                permissions=profile["permissions"],
                conditions={},
                catalog_revision=CATALOG_REVISION,
            )
            session.add(version)
            await session.flush()
        if category.status != "active" or category.scope != scope:
            raise ConflictError("Category is archived or has an incompatible scope")
        version = await self._version(
            session, category_id, revision or category.revision
        )
        return self._payload(category, version)

    async def effective_access(
        self,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        project_id: UUID | None = None,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            await self.require_permission(session, actor, workspace_id, "access:self")
            authorizer = TenantAuthorizer(session)
            permissions = set(SELF_CONTROL_PERMISSIONS)
            conditions = {}
            origin = None
            if isinstance(actor, ControlPlanePrincipal):
                permissions.update(actor.permissions)
                if project_id is not None:
                    project_workspace = await authorizer._project_workspace_id(
                        project_id
                    )
                    if project_workspace != workspace_id:
                        raise NotFoundError("Resource not found")
                    statement = text(
                        "SELECT permissions, conditions, category_id, category_revision FROM core.workspace_control_key_project_grants WHERE control_key_id=:key_id AND project_id=:project_id"
                    ).bindparams(
                        bindparam("key_id", type_=Uuid()),
                        bindparam("project_id", type_=Uuid()),
                    )
                    row = (
                        (
                            await session.execute(
                                statement,
                                {"key_id": actor.api_key_id, "project_id": project_id},
                            )
                        )
                        .mappings()
                        .first()
                    )
                    if row is None:
                        raise NotFoundError("Resource not found")
                    import json

                    granted = (
                        json.loads(row["permissions"])
                        if isinstance(row["permissions"], str)
                        else row["permissions"]
                    )
                    conditions = (
                        json.loads(row["conditions"])
                        if isinstance(row["conditions"], str)
                        else row["conditions"]
                    )
                    permissions.update(granted)
                    origin = {
                        "category_id": row["category_id"],
                        "revision": row["category_revision"],
                    }
                role = "control"
            else:
                role = await authorizer._workspace_role(actor.user_id, workspace_id)
                if project_id is not None:
                    if (
                        await authorizer._project_workspace_id(project_id)
                        != workspace_id
                    ):
                        raise NotFoundError("Resource not found")
                    await authorizer._require_project_access(
                        user_id=actor.user_id,
                        workspace_id=workspace_id,
                        project_id=project_id,
                        allow_workspace_admin=False,
                    )
                candidates = WORKSPACE_CONTROL_PERMISSIONS | (
                    PROJECT_CONTROL_PERMISSIONS if project_id else frozenset()
                )
                for permission in candidates:
                    try:
                        await authorizer.require_human_permission(
                            user_id=actor.user_id,
                            workspace_id=workspace_id,
                            project_id=project_id
                            if permission in PROJECT_CONTROL_PERMISSIONS
                            else None,
                            permission=permission,
                        )
                        permissions.add(permission)
                    except AuthorizationError:
                        pass
                assignment = (
                    await session.execute(
                        select(AuthorityAssignmentModel).where(
                            AuthorityAssignmentModel.workspace_id == workspace_id,
                            AuthorityAssignmentModel.subject_user_id == actor.user_id,
                            AuthorityAssignmentModel.scope_id
                            == (project_id or workspace_id),
                            AuthorityAssignmentModel.status == "active",
                        )
                    )
                ).scalar_one_or_none()
                if assignment:
                    origin = {
                        "category_id": assignment.category_id,
                        "revision": assignment.category_revision,
                    }
                    conditions = dict(assignment.conditions)
            return {
                "workspace_id": workspace_id,
                "project_id": project_id,
                "role": role,
                "permissions": sorted(permissions),
                "conditions": conditions,
                "origin": origin,
                "catalog_revision": CATALOG_REVISION,
                "complete": True,
            }

    async def check_access(
        self,
        *,
        actor: SecurityPrincipal,
        permission: str | None,
        path_params: dict[str, Any],
        query_params: dict[str, Any],
        body: Any,
        mutation: bool,
    ) -> dict[str, Any]:
        if permission is None:
            return {
                "allowed": False,
                "reason": "operation_unsupported",
                "permission": None,
            }
        async with self._session_factory() as session:
            authorizer = TenantAuthorizer(session)
            try:
                if isinstance(actor, ControlPlanePrincipal):
                    await authorizer.require_active_control(actor)
                    await authorizer.authorize_control_key(
                        api_key_id=actor.api_key_id,
                        workspace_id=actor.workspace_id,
                        workspace_permissions=actor.permissions,
                        required_permission=permission,
                        path_params=path_params,
                        query_params=query_params,
                        body=body,
                    )
                elif isinstance(actor, AuthenticatedPrincipal):
                    await authorizer.authorize(
                        user_id=actor.user_id,
                        path_params=path_params,
                        query_params=query_params,
                        body=body,
                        required_permission=permission,
                        mutation=mutation,
                    )
                else:
                    raise AuthorizationError("Administrative authentication required")
                return {"allowed": True, "reason": "allowed", "permission": permission}
            except AuthorizationError, NotFoundError, ConflictError:
                return {
                    "allowed": False,
                    "reason": "authority_or_resource_denied",
                    "permission": permission,
                }

    async def assign_category(
        self,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        subject_user_id: UUID,
        category_id: UUID,
        category_revision: int | None,
        project_id: UUID | None,
        expected_revision: int,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            await self.require_permission(
                session, actor, workspace_id, "categories:assign"
            )
            authorizer = TenantAuthorizer(session)
            role = await authorizer._workspace_role(subject_user_id, workspace_id)
            if role is None:
                raise NotFoundError("Resource not found")
            if role == "owner":
                raise ConflictError(
                    "Owner authority is structural and cannot be assigned"
                )
            scope = "project" if project_id else "workspace"
            if project_id:
                if await authorizer._project_workspace_id(project_id) != workspace_id:
                    raise NotFoundError("Resource not found")
                await authorizer._require_project_access(
                    user_id=subject_user_id,
                    workspace_id=workspace_id,
                    project_id=project_id,
                    allow_workspace_admin=False,
                )
            elif role != "admin":
                raise AuthorizationError(
                    "Workspace categories require administrative membership"
                )
            category = await self.resolve_category(
                workspace_id=workspace_id,
                category_id=category_id,
                revision=category_revision,
                scope=scope,
                transaction=session,
            )
            from shared.security.control_plane import is_read_permission

            if role == "viewer" and any(
                not is_read_permission(p) for p in category["permissions"]
            ):
                raise AuthorizationError("Viewer membership is read-only")
            # The assigner must also possess every delegated permission.
            for permission in category["permissions"]:
                if isinstance(actor, AuthenticatedPrincipal):
                    await authorizer.require_human_permission(
                        user_id=actor.user_id,
                        workspace_id=workspace_id,
                        project_id=project_id,
                        permission=permission,
                    )
                else:
                    await authorizer.authorize_control_key(
                        api_key_id=actor.api_key_id,
                        workspace_id=workspace_id,
                        workspace_permissions=actor.permissions,
                        required_permission=permission,
                        path_params={"project_id": project_id}
                        if project_id
                        else {"workspace_id": workspace_id},
                        query_params={},
                        body={},
                    )
            assignment = (
                await session.execute(
                    select(AuthorityAssignmentModel)
                    .where(
                        AuthorityAssignmentModel.workspace_id == workspace_id,
                        AuthorityAssignmentModel.subject_user_id == subject_user_id,
                        AuthorityAssignmentModel.scope_id
                        == (project_id or workspace_id),
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if expected_revision != (assignment.revision if assignment else 0):
                raise PreconditionFailedError("Assignment revision has changed")
            if assignment is None:
                assignment = AuthorityAssignmentModel(
                    workspace_id=workspace_id,
                    subject_user_id=subject_user_id,
                    scope_id=project_id or workspace_id,
                    project_id=project_id,
                    revision=1,
                )
                session.add(assignment)
            else:
                assignment.revision += 1
            assignment.category_id = category_id
            assignment.category_revision = category["revision"]
            assignment.permissions = list(category["permissions"])
            assignment.conditions = dict(category["conditions"])
            assignment.status = "active"
            await session.flush()
            self._audit(
                session,
                actor=actor,
                workspace_id=workspace_id,
                operation="category.assign",
                subject_id=assignment.id,
                revision=assignment.revision,
                details={
                    "subject_user_id": str(subject_user_id),
                    "project_id": str(project_id) if project_id else None,
                    "category_id": str(category_id),
                    "category_revision": category["revision"],
                },
            )
            await session.commit()
            return {
                "id": assignment.id,
                "revision": assignment.revision,
                "subject_user_id": subject_user_id,
                "project_id": project_id,
                "category_id": category_id,
                "category_revision": category["revision"],
                "permissions": assignment.permissions,
                "conditions": assignment.conditions,
            }

    async def list_audit(
        self,
        *,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        limit: int = 100,
        cursor: UUID | None = None,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 200:
            raise ValidationError("limit must be between 1 and 200")
        async with self._session_factory() as session:
            await self.require_permission(session, actor, workspace_id, "audit:read")
            query = select(AuthorityAuditModel).where(
                AuthorityAuditModel.workspace_id == workspace_id
            )
            if cursor:
                query = query.where(AuthorityAuditModel.id < cursor)
            rows = list(
                (
                    await session.execute(
                        query.order_by(AuthorityAuditModel.id.desc()).limit(limit + 1)
                    )
                ).scalars()
            )
            return {
                "items": [
                    {
                        "id": r.id,
                        "operation": r.operation,
                        "subject_id": r.subject_id,
                        "revision": r.revision,
                        "actor_user_id": r.actor_user_id,
                        "actor_control_key_id": r.actor_control_key_id,
                        "details": r.details,
                        "created_at": r.created_at,
                    }
                    for r in rows[:limit]
                ],
                "next_cursor": str(rows[limit - 1].id) if len(rows) > limit else None,
                "complete": len(rows) <= limit,
            }
