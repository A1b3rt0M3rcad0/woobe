from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.errors import AuthorizationError, ConflictError, NotFoundError

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
}

INDIRECT_PROJECT_RESOURCE_QUERIES: dict[str, str] = {
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

WORKSPACE_KEYS = {"workspace_id", "workspace_id"}


def _is_identifier_key(key: object) -> bool:
    return (
        key in WORKSPACE_KEYS
        or key == "project_id"
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
    return [
        (str(key), item)
        for key, item in value.items()
        if _is_identifier_key(key)
    ]


def _uuid(value: Any) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


class TenantAuthorizer:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def authorize(
        self,
        *,
        user_id: UUID,
        path_params: Mapping[str, Any],
        query_params: Mapping[str, Any],
        body: Any,
        allow_workspace_admin_for_projects: bool = False,
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
                if key == "project_id"
                else await self._project_id_for_resource(key, resource_id)
            )
            if project_id is None:
                raise NotFoundError("Resource not found")
            request_projects.add(project_id)
            if len(request_projects) > 1:
                raise ConflictError("Resources from different projects cannot be combined")
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
                if key == "project_id"
                else await self._project_id_for_resource(key, resource_id)
            )
            if resolved_project_id is None or resolved_project_id != project_id:
                raise NotFoundError("Resource not found")
            checked_context = True

        if not checked_context:
            raise AuthorizationError("Project context is required for API key access")

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
            text("SELECT workspace_id FROM core.projects WHERE id = :project_id"),
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
            ),
            {"user_id": user_id, "project_id": project_id},
        )
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Resource not found")
