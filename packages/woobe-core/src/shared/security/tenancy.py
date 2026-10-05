from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Uuid, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
)
from shared.security.principal import ControlPlanePrincipal
from shared.security.control_plane import (
    PROJECT_CONTROL_PERMISSIONS,
    WORKSPACE_CONTROL_PERMISSIONS,
    SELF_CONTROL_PERMISSIONS,
    is_read_permission,
    conditions_allow,
)

DIRECT_PROJECT_RESOURCES: dict[str, str] = {
    "api_key_id": "core.api_keys",
    "surface_id": "chat_surface.chat_surfaces",
    "chat_surface_id": "chat_surface.chat_surfaces",
    "agent_id": "agent.agents",
    "credential_id": "agent.provider_credentials",
    "provider_credential_id": "agent.provider_credentials",
    "fallback_credential_id": "agent.provider_credentials",
    "provider_model_id": "agent.provider_models",
    "fallback_provider_model_id": "agent.provider_models",
    "embedding_provider_model_id": "agent.provider_models",
    "collection_id": "agent.document_collections",
    "document_id": "agent.documents",
    "snapshot_id": "agent.vector_snapshots",
    "vector_snapshot_id": "agent.vector_snapshots",
    "tool_id": "agent.tools",
    "skill_id": "agent.skills",
    "secret_id": "agent.tool_secrets",
    "session_id": "agent.sessions",
    "message_id": "agent.messages",
    "job_id": "agent.ask_jobs",
    "ask_job_id": "agent.ask_jobs",
    "release_id": "agent.agent_releases",
    "release_test_id": "agent.agent_release_tests",
    "contract_id": "agent.agent_contracts",
    "config_id": "agent.agent_model_configs",
    "prompt_id": "agent.agent_prompts",
    # The current prompt-version route names this identifier `version_id`.
    "version_id": "agent.agent_prompts",
    "knowledge_version_id": "agent.knowledge_versions",
    "trace_id": "observability.traces",
    "run_id": "agent.agent_runs",
    "network_id": "network.networks",
    "execution_id": "network.network_executions",
    "network_session_id": "network.network_sessions",
}

INDIRECT_PROJECT_RESOURCE_QUERIES: dict[str, str] = {
    "network_version_id": """
        SELECT networks.project_id FROM network.network_versions AS versions
        JOIN network.networks AS networks ON networks.id = versions.network_id
        WHERE versions.id = :resource_id
    """,
    "run_trace_id": """
        SELECT project_id
        FROM agent.agent_runs
        WHERE trace_id = :resource_id
        LIMIT 1
    """,
    "skill_version_id": """
        SELECT skills.project_id
        FROM agent.skill_versions AS versions
        JOIN agent.skills AS skills ON skills.id = versions.skill_id
        WHERE versions.id = :resource_id
    """,
    # agent_collections does not duplicate project_id; ownership is derived from
    # its agent. This is used by DELETE /knowledge/agent-collections/{link_id}.
    "link_id": """
        SELECT agents.project_id
        FROM agent.agent_collections AS links
        JOIN agent.agents AS agents ON agents.id = links.agent_id
        WHERE links.id = :resource_id
    """,
}

WORKSPACE_KEYS = {"workspace_id"}
PROJECT_KEYS = {"project_id", "access_project_id"}


def _is_identifier_key(key: object) -> bool:
    return (
        key in WORKSPACE_KEYS
        or key in PROJECT_KEYS
        or key in DIRECT_PROJECT_RESOURCES
        or key in INDIRECT_PROJECT_RESOURCE_QUERIES
    )


def _identifier_values(value: Any) -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _is_identifier_key(key):
                found.append((str(key), item))
            elif isinstance(item, (Mapping, list, tuple)):
                found.extend(_identifier_values(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_identifier_values(item))
    return found


def _direct_identifier_values(value: Any) -> list[tuple[str, Any]]:
    if not isinstance(value, Mapping):
        return []
    return [(str(key), item) for key, item in value.items() if _is_identifier_key(key)]


def _uuid(value: Any) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except ValueError, TypeError, AttributeError:
        return None


class TenantAuthorizer:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def require_active_control(self, actor: ControlPlanePrincipal) -> None:
        statement = """SELECT keys.permissions, keys.status, keys.revoked_at, keys.expires_at,
            keys.on_project_create_permissions, workspaces.status AS workspace_status
            FROM core.workspace_control_keys AS keys
            JOIN identity.workspaces AS workspaces ON workspaces.id = keys.workspace_id
            WHERE keys.id = :id AND keys.workspace_id = :workspace_id"""
        if (
            self._session.bind is not None
            and self._session.bind.dialect.name == "postgresql"
        ):
            statement += " FOR SHARE OF keys, workspaces"
        row = (
            (
                await self._session.execute(
                    text(statement).bindparams(
                        bindparam("id", type_=Uuid()),
                        bindparam("workspace_id", type_=Uuid()),
                    ),
                    {"id": actor.api_key_id, "workspace_id": actor.workspace_id},
                )
            )
            .mappings()
            .first()
        )
        if (
            row is None
            or row["status"] != "active"
            or row["revoked_at"] is not None
            or row["workspace_status"] != "active"
        ):
            raise AuthenticationError("Control credential is inactive")
        expiry = row["expires_at"]
        if isinstance(expiry, str):
            expiry = datetime.fromisoformat(expiry)
        if expiry is not None and expiry.replace(
            tzinfo=expiry.tzinfo or UTC
        ) <= datetime.now(UTC):
            raise AuthenticationError("Control credential is expired")
        import json

        permissions = row["permissions"]
        creation = row["on_project_create_permissions"]
        if isinstance(permissions, str):
            permissions = json.loads(permissions)
        if isinstance(creation, str):
            creation = json.loads(creation)
        if (
            frozenset(permissions) != actor.permissions
            or frozenset(creation) != actor.on_project_create_permissions
        ):
            raise AuthenticationError(
                "Control credential changed; retry authentication"
            )

    async def authorize(
        self,
        *,
        user_id: UUID,
        path_params: Mapping[str, Any],
        query_params: Mapping[str, Any],
        body: Any,
        allow_workspace_admin_for_projects: bool = False,
        required_permission: str | None = None,
        mutation: bool = False,
    ) -> None:
        identifiers = self._identifiers(path_params, query_params, body)
        self._require_consistent_identifiers(
            self._consistency_identifiers(path_params, query_params, body)
        )

        checked_workspaces: set[UUID] = set()
        checked_projects: set[UUID] = set()
        request_projects: set[UUID] = set()

        for key, raw_value in identifiers:
            resource_id = _uuid(raw_value)
            if resource_id is None:
                continue
            if key in WORKSPACE_KEYS:
                if resource_id not in checked_workspaces:
                    await self._require_membership(user_id, resource_id)
                    checked_workspaces.add(resource_id)
                continue

            project_id = (
                resource_id
                if key in PROJECT_KEYS
                else await self._project_id_for_resource(key, resource_id)
            )
            if project_id is None:
                raise NotFoundError("Resource not found")
            request_projects.add(project_id)
            if len(request_projects) > 1 and required_permission not in {
                "keys:create",
                "keys:update",
            }:
                raise ConflictError(
                    "Resources from different projects cannot be combined"
                )
            if project_id in checked_projects:
                continue

            workspace_id = await self._project_workspace_id(project_id)
            if workspace_id is None:
                raise NotFoundError("Resource not found")
            await self._require_project_access(
                user_id=user_id,
                workspace_id=workspace_id,
                project_id=project_id,
                allow_workspace_admin=allow_workspace_admin_for_projects,
            )
            checked_projects.add(project_id)
            checked_workspaces.add(workspace_id)

        if required_permission is not None or mutation:
            permission = required_permission or "operation:mutation"
            if (
                checked_projects
                and required_permission not in WORKSPACE_CONTROL_PERMISSIONS
            ):
                for project_id in checked_projects:
                    workspace_id = await self._project_workspace_id(project_id)
                    await self.require_human_permission(
                        user_id=user_id,
                        workspace_id=workspace_id,
                        project_id=project_id,
                        permission=permission,
                    )
            else:
                for workspace_id in checked_workspaces:
                    await self.require_human_permission(
                        user_id=user_id,
                        workspace_id=workspace_id,
                        project_id=None,
                        permission=permission,
                    )

    async def authorize_api_key(
        self,
        *,
        project_id: UUID,
        path_params: Mapping[str, Any],
        query_params: Mapping[str, Any],
        body: Any,
    ) -> None:
        identifiers = self._identifiers(path_params, query_params, body)
        self._require_consistent_identifiers(
            self._consistency_identifiers(path_params, query_params, body)
        )
        checked_context = False
        for key, raw_value in identifiers:
            resource_id = _uuid(raw_value)
            if resource_id is None:
                continue
            if key in WORKSPACE_KEYS:
                raise NotFoundError("Resource not found")
            resolved_project_id = (
                resource_id
                if key in PROJECT_KEYS
                else await self._project_id_for_resource(key, resource_id)
            )
            if resolved_project_id is None or resolved_project_id != project_id:
                raise NotFoundError("Resource not found")
            checked_context = True

        if not checked_context:
            raise AuthorizationError("Project context is required for API key access")

    async def authorize_control_key(
        self,
        *,
        api_key_id: UUID,
        workspace_id: UUID,
        workspace_permissions: frozenset[str],
        required_permission: str,
        path_params: Mapping[str, Any],
        query_params: Mapping[str, Any],
        body: Any,
    ) -> None:
        identifiers = self._identifiers(path_params, query_params, body)
        self._require_consistent_identifiers(
            self._consistency_identifiers(path_params, query_params, body)
        )

        if required_permission in WORKSPACE_CONTROL_PERMISSIONS:
            if required_permission not in workspace_permissions:
                raise AuthorizationError("Control key permission is not sufficient")
        elif (
            required_permission not in PROJECT_CONTROL_PERMISSIONS
            and required_permission not in SELF_CONTROL_PERMISSIONS
        ):
            raise AuthorizationError(
                "Control key access is not allowed for this endpoint"
            )

        checked_projects: set[UUID] = set()
        request_projects: set[UUID] = set()
        checked_context = False

        for key, raw_value in identifiers:
            resource_id = _uuid(raw_value)
            if resource_id is None:
                continue

            if key in WORKSPACE_KEYS:
                if resource_id != workspace_id:
                    raise NotFoundError("Resource not found")
                checked_context = True
                continue

            project_id = (
                resource_id
                if key in PROJECT_KEYS
                else await self._project_id_for_resource(key, resource_id)
            )
            if project_id is None:
                raise NotFoundError("Resource not found")

            request_projects.add(project_id)
            if len(request_projects) > 1 and required_permission not in {
                "keys:create",
                "keys:update",
            }:
                raise ConflictError(
                    "Resources from different projects cannot be combined"
                )

            project_workspace_id = await self._project_workspace_id(project_id)
            if project_workspace_id is None or project_workspace_id != workspace_id:
                raise NotFoundError("Resource not found")

            checked_context = True
            if required_permission in PROJECT_CONTROL_PERMISSIONS:
                if project_id not in checked_projects:
                    await self._require_control_key_project_permission(
                        api_key_id=api_key_id,
                        project_id=project_id,
                        permission=required_permission,
                        context=body,
                        path_context=path_params,
                    )
                    checked_projects.add(project_id)

        if required_permission in PROJECT_CONTROL_PERMISSIONS and not checked_projects:
            raise AuthorizationError(
                "Project context is required for control key access"
            )
        if required_permission in WORKSPACE_CONTROL_PERMISSIONS and not checked_context:
            raise AuthorizationError(
                "Workspace context is required for control key access"
            )

    async def require_human_permission(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        project_id: UUID | None,
        permission: str,
    ) -> None:
        role = await self._workspace_role(user_id, workspace_id)
        if role is None:
            raise NotFoundError("Resource not found")
        if role == "owner":
            return
        if role == "viewer" and not is_read_permission(permission):
            raise AuthorizationError("Viewer membership is read-only")
        if permission in SELF_CONTROL_PERMISSIONS or (
            project_id is None and permission in {"workspace:read", "categories:read"}
        ):
            return
        if project_id is None:
            if role != "admin":
                raise AuthorizationError(
                    "Workspace administrative authority is required"
                )
        else:
            if role == "admin" and permission.startswith("project:access:"):
                return
            await self._require_project_access(
                user_id=user_id,
                workspace_id=workspace_id,
                project_id=project_id,
                allow_workspace_admin=False,
            )
        scope_id = project_id or workspace_id
        statement = text(
            "SELECT permissions FROM identity.authority_assignments WHERE workspace_id = :workspace_id AND subject_user_id = :user_id AND scope_id = :scope_id AND status = 'active'"
        ).bindparams(
            bindparam("workspace_id", type_=Uuid()),
            bindparam("user_id", type_=Uuid()),
            bindparam("scope_id", type_=Uuid()),
        )
        grants = (
            await self._session.execute(
                statement,
                {
                    "workspace_id": workspace_id,
                    "user_id": user_id,
                    "scope_id": scope_id,
                },
            )
        ).scalar_one_or_none()
        if grants is not None:
            if isinstance(grants, str):
                import json

                grants = json.loads(grants)
            if permission not in grants:
                raise AuthorizationError(
                    "Assigned authority does not allow this operation"
                )

    async def _require_control_key_project_permission(
        self,
        *,
        api_key_id: UUID,
        project_id: UUID,
        permission: str,
        context: Any = None,
        path_context: Mapping[str, Any] | None = None,
    ) -> None:
        result = await self._session.execute(
            text(
                """
                SELECT permissions, conditions
                FROM core.workspace_control_key_project_grants
                WHERE control_key_id = :api_key_id
                  AND project_id = :project_id
                """
            ),
            {"api_key_id": api_key_id, "project_id": project_id},
        )
        row = result.first()
        if row is None:
            raise NotFoundError("Resource not found")
        permissions, conditions = row
        granted = {str(item) for item in (permissions or [])}
        if permission not in granted:
            raise AuthorizationError("Control key Project permission is not sufficient")
        data = context if isinstance(context, Mapping) else {}
        path_data = path_context or {}
        target_id = (
            data.get("target_id")
            or data.get("agent_id")
            or data.get("network_id")
            or path_data.get("agent_id")
            or path_data.get("network_id")
        )
        target_type = data.get("target_type") or (
            "agent"
            if data.get("agent_id") or path_data.get("agent_id")
            else "network"
            if data.get("network_id") or path_data.get("network_id")
            else None
        )
        environment = data.get("environment")
        if permission.endswith(":production"):
            environment = "production"
        if not conditions_allow(
            conditions or {},
            environment=environment,
            target_type=target_type,
            target_id=target_id,
            interfaces=data.get("interfaces"),
        ):
            raise AuthorizationError("Grant conditions do not allow this operation")

    @staticmethod
    def _identifiers(
        path_params: Mapping[str, Any],
        query_params: Mapping[str, Any],
        body: Any,
    ) -> list[tuple[str, Any]]:
        return (
            _identifier_values(path_params)
            + _identifier_values(query_params)
            + _identifier_values(body)
        )

    @staticmethod
    def _consistency_identifiers(
        path_params: Mapping[str, Any],
        query_params: Mapping[str, Any],
        body: Any,
    ) -> list[tuple[str, Any]]:
        return (
            _direct_identifier_values(path_params)
            + _direct_identifier_values(query_params)
            + _direct_identifier_values(body)
        )

    @staticmethod
    def _require_consistent_identifiers(identifiers: list[tuple[str, Any]]) -> None:
        values_by_key: dict[str, UUID] = {}
        for key, raw_value in identifiers:
            value = _uuid(raw_value)
            if value is None:
                continue
            previous = values_by_key.get(key)
            if previous is not None and previous != value:
                raise ConflictError(f"Conflicting {key} values in request")
            values_by_key[key] = value

    async def _project_id_for_resource(
        self,
        key: str,
        resource_id: UUID,
    ) -> UUID | None:
        indirect_query = INDIRECT_PROJECT_RESOURCE_QUERIES.get(key)
        if indirect_query is not None:
            result = await self._session.execute(
                text(indirect_query),
                {"resource_id": resource_id},
            )
            value = result.scalar_one_or_none()
            return UUID(str(value)) if value is not None else None

        table = DIRECT_PROJECT_RESOURCES.get(key)
        if table is None:
            return None
        allowed_tables = set(DIRECT_PROJECT_RESOURCES.values())
        if table not in allowed_tables:
            raise RuntimeError("Unsupported tenant resource mapping")
        result = await self._session.execute(
            text(f"SELECT project_id FROM {table} WHERE id = :resource_id"),
            {"resource_id": resource_id},
        )
        value = result.scalar_one_or_none()
        return UUID(str(value)) if value is not None else None

    async def _project_workspace_id(self, project_id: UUID) -> UUID | None:
        result = await self._session.execute(
            text(
                "SELECT workspace_id FROM core.projects WHERE id = :project_id"
            ).bindparams(bindparam("project_id", type_=Uuid())),
            {"project_id": project_id},
        )
        value = result.scalar_one_or_none()
        return UUID(str(value)) if value is not None else None

    async def _workspace_role(self, user_id: UUID, workspace_id: UUID) -> str | None:
        result = await self._session.execute(
            text(
                """
                SELECT role
                FROM identity.workspace_members
                WHERE user_id = :user_id
                  AND workspace_id = :workspace_id
                  AND status = 'active'
                """
            ).bindparams(
                bindparam("user_id", type_=Uuid()),
                bindparam("workspace_id", type_=Uuid()),
            ),
            {"user_id": user_id, "workspace_id": workspace_id},
        )
        role = result.scalar_one_or_none()
        return str(role) if role is not None else None

    async def _require_membership(self, user_id: UUID, workspace_id: UUID) -> None:
        if await self._workspace_role(user_id, workspace_id) is None:
            raise NotFoundError("Resource not found")

    async def _require_project_access(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        allow_workspace_admin: bool,
    ) -> None:
        role = await self._workspace_role(user_id, workspace_id)
        if role is None:
            raise NotFoundError("Resource not found")
        if role == "owner" or (allow_workspace_admin and role == "admin"):
            return

        result = await self._session.execute(
            text(
                """
                SELECT 1
                FROM core.project_members
                WHERE user_id = :user_id
                  AND project_id = :project_id
                  AND status = 'active'
                """
            ).bindparams(
                bindparam("user_id", type_=Uuid()),
                bindparam("project_id", type_=Uuid()),
            ),
            {"user_id": user_id, "project_id": project_id},
        )
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Resource not found")
