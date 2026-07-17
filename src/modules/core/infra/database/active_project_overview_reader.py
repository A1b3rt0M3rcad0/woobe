from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.core.application.dtos.project_overview import (
    OverviewBucket,
    OverviewEnvironment,
)
from modules.core.infra.database.uow_project_overview_reader import UnitOfWorkProjectOverviewReader


class ActiveDocumentProjectOverviewReader(UnitOfWorkProjectOverviewReader):
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
        network_metrics = await self._network_summary(
            self._uow.session,
            {
                "project_id": project_id,
                "start": start,
                "end": end,
                "environment": environment,
            },
        )
        sections["summary"].update(network_metrics)
        return sections

    async def _network_summary(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> dict[str, int]:
        statement = text(
            """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM network.networks AS network
                    WHERE network.project_id = :project_id
                ) AS network_count,
                (
                    SELECT COUNT(*)
                    FROM network.networks AS network
                    WHERE network.project_id = :project_id
                      AND network.staging_version_id IS NOT NULL
                ) AS staging_networks,
                (
                    SELECT COUNT(*)
                    FROM network.networks AS network
                    WHERE network.project_id = :project_id
                      AND network.production_version_id IS NOT NULL
                ) AS production_networks,
                (
                    SELECT COUNT(*)
                    FROM network.network_executions AS execution
                    JOIN network.network_sessions AS network_session
                      ON network_session.id = execution.network_session_id
                    WHERE execution.project_id = :project_id
                      AND execution.created_at >= :start
                      AND execution.created_at < :end
                      AND (
                        :environment = 'all'
                        OR network_session.environment = :environment
                      )
                ) AS network_runs,
                (
                    SELECT COUNT(*)
                    FROM network.network_executions AS execution
                    JOIN network.network_sessions AS network_session
                      ON network_session.id = execution.network_session_id
                    WHERE execution.project_id = :project_id
                      AND execution.created_at >= :start
                      AND execution.created_at < :end
                      AND execution.status IN ('failed', 'timed_out', 'uncertain')
                      AND (
                        :environment = 'all'
                        OR network_session.environment = :environment
                      )
                ) AS failed_network_runs
            """
        )
        row = (await session.execute(statement, params)).mappings().one()
        return {key: int(row[key] or 0) for key in row.keys()}

    async def _knowledge_summary(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> dict[str, int]:
        statement = text(
            """
            WITH active_documents AS (
                SELECT *
                FROM agent.documents
                WHERE project_id = :project_id
                  AND status <> 'deleted'
            )
            SELECT
                (
                    SELECT COUNT(*)
                    FROM agent.document_collections
                    WHERE project_id = :project_id
                      AND status <> 'deleted'
                ) AS collections,
                COUNT(*) AS documents,
                COUNT(*) FILTER (
                    WHERE indexed_at IS NOT NULL OR status IN ('ready', 'indexed')
                ) AS indexed_documents,
                COUNT(*) FILTER (
                    WHERE status IN ('failed', 'error')
                ) AS failed_documents,
                COALESCE(SUM(size_bytes), 0) AS storage_bytes,
                COUNT(*) FILTER (
                    WHERE indexed_at IS NULL
                      AND status NOT IN ('failed', 'error', 'ready', 'indexed')
                ) AS pending_documents
            FROM active_documents
            """
        )
        row = (await session.execute(statement, params)).mappings().one()
        return {key: int(row[key] or 0) for key in row.keys()}
