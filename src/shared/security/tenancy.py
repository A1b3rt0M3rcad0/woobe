from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.errors import NotFoundError


DIRECT_PROJECT_RESOURCES: dict[str, str] = {
    "api_key_id": "core.api_keys",
    "agent_id": "agent.agents",
    "credential_id": "agent.provider_credentials",
    "provider_credential_id": "agent.provider_credentials",
    "fallback_credential_id": "agent.provider_credentials",
    "collection_id": "agent.document_collections",
    "document_id": "agent.documents",
    "tool_id": "agent.tools",
    "secret_id": "agent.tool_secrets",
    "session_id": "agent.sessions",
    "message_id": "agent.messages",
    "job_id": "agent.ask_jobs",
    "ask_job_id": "agent.ask_jobs",
    "release_id": "agent.agent_releases",
    "contract_id": "agent.agent_contracts",
    "config_id": "agent.agent_model_configs",
    "trace_id": "observability.traces",
}
ORGANIZATION_KEYS = {"organization_id", "org_id"}


def _identifier_values(value: Any) -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in ORGANIZATION_KEYS or key == "project_id" or key in DIRECT_PROJECT_RESOURCES:
                found.append((key, item))
            elif isinstance(item, (Mapping, list, tuple)):
                found.extend(_identifier_values(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_identifier_values(item))
    return found


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
    ) -> None:
        identifiers = (
            _identifier_values(path_params)
            + _identifier_values(query_params)
            + _identifier_values(body)
        )
        checked_organizations: set[UUID] = set()
        checked_projects: set[UUID] = set()

        for key, raw_value in identifiers:
            resource_id = _uuid(raw_value)
            if resource_id is None:
                continue
            if key in ORGANIZATION_KEYS:
                if resource_id not in checked_organizations:
                    await self._require_membership(user_id, resource_id)
                    checked_organizations.add(resource_id)
                continue

            project_id = resource_id if key == "project_id" else await self._project_id_for_resource(key, resource_id)
            if project_id is None:
                raise NotFoundError("Resource not found")
            if project_id in checked_projects:
                continue

            organization_id = await self._project_organization_id(project_id)
            if organization_id is None:
                raise NotFoundError("Resource not found")
            await self._require_membership(user_id, organization_id)
            checked_projects.add(project_id)
            checked_organizations.add(organization_id)

    async def _project_id_for_resource(self, key: str, resource_id: UUID) -> UUID | None:
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
        return result.scalar_one_or_none()

    async def _project_organization_id(self, project_id: UUID) -> UUID | None:
        result = await self._session.execute(
            text("SELECT organization_id FROM core.projects WHERE id = :project_id"),
            {"project_id": project_id},
        )
        return result.scalar_one_or_none()

    async def _require_membership(self, user_id: UUID, organization_id: UUID) -> None:
        result = await self._session.execute(
            text(
                """
                SELECT 1
                FROM identity.organization_members
                WHERE user_id = :user_id
                  AND organization_id = :organization_id
                  AND status = 'active'
                """
            ),
            {"user_id": user_id, "organization_id": organization_id},
        )
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Resource not found")
