from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.core.infra.database.uow_project_overview_reader import UnitOfWorkProjectOverviewReader


class ActiveDocumentProjectOverviewReader(UnitOfWorkProjectOverviewReader):
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
