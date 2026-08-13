from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.core.application.dtos.project_overview import (
    OverviewBucket,
    OverviewEnvironment,
)
from modules.core.infra.database.active_project_overview_reader import (
    ActiveDocumentProjectOverviewReader,
)


class ContextualProjectOverviewReader(ActiveDocumentProjectOverviewReader):
    """Adds a compact, environment-aware change timeline to the Overview."""

    query_count = 13

    async def fetch(
        self,
        *,
        project_id: UUID,
        start: datetime,
        end: datetime,
        bucket: OverviewBucket,
        environment: OverviewEnvironment,
        recent_limit: int,
    ) -> dict[str, Any]:
        sections = await super().fetch(
            project_id=project_id,
            start=start,
            end=end,
            bucket=bucket,
            environment=environment,
            recent_limit=recent_limit,
        )
        params = {
            "project_id": project_id,
            "start": start,
            "end": end,
            "environment": environment,
            "recent_limit": recent_limit,
            "bucket": bucket,
            "step": timedelta(hours=1) if bucket == "hour" else timedelta(days=1),
        }
        sections["recent_changes"] = await self._recent_changes(
            self._uow.session,
            params,
        )
        return sections

    async def _recent_changes(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        statement = text(
            """
            WITH changes AS (
                SELECT
                    release.id,
                    'agent'::text AS resource_type,
                    release.agent_id AS resource_id,
                    agent.name AS resource_name,
                    release.status AS environment,
                    CASE release.status
                        WHEN 'draft' THEN 'draft_updated'
                        WHEN 'staging' THEN 'staged'
                        ELSE 'released'
                    END AS action,
                    release.version,
                    NULL::integer AS revision,
                    release.release_notes AS description,
                    CASE release.status
                        WHEN 'draft' THEN release.updated_at
                        ELSE COALESCE(release.promoted_at, release.created_at)
                    END AS occurred_at,
                    release.status <> 'draft' AS immutable
                FROM agent.agent_releases AS release
                JOIN agent.agents AS agent
                  ON agent.id = release.agent_id
                 AND agent.project_id = :project_id
                WHERE release.project_id = :project_id
                  AND release.status IN ('draft', 'staging', 'production')
                  AND (
                    :environment = 'all'
                    OR release.status = :environment
                  )
                  AND CASE release.status
                        WHEN 'draft' THEN release.updated_at
                        ELSE COALESCE(release.promoted_at, release.created_at)
                      END >= :start
                  AND CASE release.status
                        WHEN 'draft' THEN release.updated_at
                        ELSE COALESCE(release.promoted_at, release.created_at)
                      END < :end

                UNION ALL

                SELECT
                    network.id,
                    'network'::text AS resource_type,
                    network.id AS resource_id,
                    network.name AS resource_name,
                    'draft'::text AS environment,
                    'draft_updated'::text AS action,
                    NULL::varchar AS version,
                    network.draft_revision AS revision,
                    NULLIF(network.description, '') AS description,
                    network.updated_at AS occurred_at,
                    FALSE AS immutable
                FROM network.networks AS network
                WHERE network.project_id = :project_id
                  AND (:environment = 'all' OR :environment = 'draft')
                  AND network.updated_at >= :start
                  AND network.updated_at < :end

                UNION ALL

                SELECT
                    version.id,
                    'network'::text AS resource_type,
                    version.network_id AS resource_id,
                    network.name AS resource_name,
                    CASE version.kind
                        WHEN 'release' THEN 'production'
                        ELSE 'staging'
                    END AS environment,
                    CASE
                        WHEN version.activation_kind = 'rollback' THEN 'rolled_back'
                        WHEN version.activation_kind = 'reactivate' THEN 'reactivated'
                        WHEN version.kind = 'staging' THEN 'staged'
                        ELSE 'released'
                    END AS action,
                    version.version,
                    NULL::integer AS revision,
                    version.change_description AS description,
                    version.created_at AS occurred_at,
                    TRUE AS immutable
                FROM network.network_versions AS version
                JOIN network.networks AS network
                  ON network.id = version.network_id
                 AND network.project_id = :project_id
                WHERE version.project_id = :project_id
                  AND version.kind IN ('staging', 'release')
                  AND version.created_at >= :start
                  AND version.created_at < :end
                  AND (
                    :environment = 'all'
                    OR (:environment = 'staging' AND version.kind = 'staging')
                    OR (:environment = 'production' AND version.kind = 'release')
                  )
            )
            SELECT
                id,
                resource_type,
                resource_id,
                resource_name,
                environment,
                action,
                version,
                revision,
                description,
                occurred_at,
                immutable
            FROM changes
            ORDER BY occurred_at DESC, id DESC
            LIMIT :recent_limit
            """
        )
        return [
            dict(row)
            for row in (await session.execute(statement, params)).mappings().all()
        ]
