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
    "version_id": "agent.agent_prompts",
    "knowledge_version_id": "agent.knowledge_versions",
    "trace_id": "observability.traces",
}

INDIRECT_PROJECT_RESOURCE_QUERIES = {
    "link_id": """
        SELECT agents.project_id
        FROM agent.agent_collections links
        JOIN agent.agents agents ON agents.id = links.agent_id
        WHERE links.id = :resource_id
    """
}


def _uuid(value: Any) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _values(value: Any) -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "project_id" or key in DIRECT_PROJECT_RESOURCES or key in INDIRECT_PROJECT_RESOURCE_QUERIES:
                found.append((str(key), item))
            elif isinstance(item, (Mapping, list, tuple)):
                found.extend(_values(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_values(item))
    return found


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
    ) -> None:
        identifiers = _values(path_params) + _values(query_params) + _values(body)
        self._require_consistent(identifiers)
        if not identifiers or await self._is_admin(user_id):
            return
        projects: set[UUID] = set()
        for key, raw in identifiers:
            resource_id = _uuid(raw)
            if resource_id is None:
                continue
            project_id = resource_id if key == "project_id" else await self._project_for(key, resource_id)
            if project_id is None:
                raise NotFoundError("Resource not found")
            projects.add(project_id)
            if len(projects) > 1:
                raise ConflictError("Resources from different projects cannot be combined")
        for project_id in projects:
            await self._require_project_access(user_id, project_id)

    async def authorize_api_key(
        self,
        *,
        project_id: UUID,
        path_params: Mapping[str, Any],
        query_params: Mapping[str, Any],
        body: Any,
    ) -> None:
        identifiers = _values(path_params) + _values(query_params) + _values(body)
        self._require_consistent(identifiers)
        checked = False
        for key, raw in identifiers:
            resource_id = _uuid(raw)
            if resource_id is None:
                continue
            resolved = resource_id if key == "project_id" else await self._project_for(key, resource_id)
            if resolved is None or resolved != project_id:
                raise NotFoundError("Resource not found")
            checked = True
        if not checked:
            raise AuthorizationError("Project context is required for API key access")

    @staticmethod
    def _require_consistent(identifiers: list[tuple[str, Any]]) -> None:
        seen: dict[str, UUID] = {}
        for key, raw in identifiers:
            value = _uuid(raw)
            if value is None:
                continue
            previous = seen.get(key)
            if previous is not None and previous != value:
                raise ConflictError(f"Conflicting {key} values in request")
            seen[key] = value

    async def _project_for(self, key: str, resource_id: UUID) -> UUID | None:
        indirect = INDIRECT_PROJECT_RESOURCE_QUERIES.get(key)
        if indirect:
            result = await self._session.execute(text(indirect), {"resource_id": resource_id})
        else:
            table = DIRECT_PROJECT_RESOURCES.get(key)
            if table is None:
                return None
            result = await self._session.execute(
                text(f"SELECT project_id FROM {table} WHERE id = :resource_id"),
                {"resource_id": resource_id},
            )
        value = result.scalar_one_or_none()
        return UUID(str(value)) if value is not None else None

    async def _is_admin(self, user_id: UUID) -> bool:
        result = await self._session.execute(text("""
            SELECT 1 FROM identity.instance_settings
            WHERE id = 1 AND admin_user_id = :user_id AND initialized_at IS NOT NULL
        """), {"user_id": user_id})
        return result.scalar_one_or_none() is not None

    async def _require_project_access(self, user_id: UUID, project_id: UUID) -> None:
        result = await self._session.execute(text("""
            SELECT 1
            FROM core.projects p
            JOIN core.workspace_members wm
              ON wm.workspace_id = p.workspace_id
             AND wm.user_id = :user_id
             AND wm.status = 'active'
            JOIN core.project_members pm
              ON pm.project_id = p.id
             AND pm.user_id = :user_id
             AND pm.status = 'active'
            WHERE p.id = :project_id
        """), {"user_id": user_id, "project_id": project_id})
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Resource not found")
