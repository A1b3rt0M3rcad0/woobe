from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.core.application.dtos.project_overview import (
    OverviewBucket,
    OverviewEnvironment,
)
from modules.core.infra.database.project_overview_reader import (
    SQLAlchemyProjectOverviewReader,
)
from shared.infra.errors import NotFoundError


class _CoreSessionProvider(Protocol):
    @property
    def session(self) -> AsyncSession: ...


class UnitOfWorkProjectOverviewReader(SQLAlchemyProjectOverviewReader):
    """Project overview reader bound to the active CoreUnitOfWork session."""

    def __init__(self, uow: _CoreSessionProvider) -> None:
        self._uow = uow

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
        params = {
            "project_id": project_id,
            "start": start,
            "end": end,
            "previous_start": start - (end - start),
            "environment": environment,
            "recent_limit": recent_limit,
            "bucket": bucket,
            "step": timedelta(hours=1) if bucket == "hour" else timedelta(days=1),
        }
        session = self._uow.session
        summary = await self._summary(session, params)
        timeseries = await self._timeseries(session, params)
        distribution = await self._environment_distribution(session, params)
        releases = await self._recent_releases(session, params)
        traces = await self._recent_traces(session, params)
        knowledge = await self._knowledge_summary(session, params)
        tools = await self._tools_summary(session, params)

        if not summary.pop("project_exists"):
            raise NotFoundError("Project not found")

        return {
            "summary": summary,
            "timeseries": timeseries,
            "environment_distribution": distribution,
            "recent_releases": releases,
            "recent_traces": traces,
            "knowledge_summary": knowledge,
            "tools_summary": tools,
            "capabilities": {
                "sessions_jobs": False,
                "ingestion_pipeline": False,
                "activity_feed": False,
            },
        }

    async def _timeseries(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        statement = text(
            f"""
            WITH {self._agent_environment_cte()},
            trace_buckets AS (
                SELECT
                    date_trunc(:bucket, trace.started_at, 'UTC') AS bucket_start,
                    COUNT(*) AS requests,
                    COUNT(*) FILTER (
                        WHERE trace.status = 'completed'
                    ) AS success,
                    COUNT(*) FILTER (
                        WHERE trace.status IN ('failed', 'cancelled')
                    ) AS failed,
                    AVG(trace.total_latency_ms) FILTER (
                        WHERE trace.total_latency_ms IS NOT NULL
                    ) AS avg_latency_ms,
                    percentile_cont(0.95) WITHIN GROUP (
                        ORDER BY trace.total_latency_ms
                    ) FILTER (
                        WHERE trace.total_latency_ms IS NOT NULL
                    ) AS p95_latency_ms,
                    SUM(
                        CASE
                            WHEN COALESCE(trace.data ->> 'input_tokens', '') ~ '^[0-9]+$'
                            THEN (trace.data ->> 'input_tokens')::bigint
                            ELSE 0
                        END
                    ) AS input_tokens,
                    SUM(
                        CASE
                            WHEN COALESCE(trace.data ->> 'output_tokens', '') ~ '^[0-9]+$'
                            THEN (trace.data ->> 'output_tokens')::bigint
                            ELSE 0
                        END
                    ) AS output_tokens,
                    SUM(trace.total_cost_usd) FILTER (
                        WHERE trace.total_cost_usd IS NOT NULL
                    ) AS known_cost_usd,
                    COUNT(*) FILTER (
                        WHERE trace.total_cost_usd IS NOT NULL
                    ) AS known_cost_count,
                    COUNT(*) FILTER (
                        WHERE trace.total_cost_usd IS NULL
                    ) AS unknown_cost_count
                FROM observability.traces AS trace
                LEFT JOIN agent_environment
                    ON agent_environment.agent_id = trace.agent_id
                WHERE trace.project_id = :project_id
                  AND trace.started_at >= :start
                  AND trace.started_at < :end
                  AND trace.status IN ('completed', 'failed', 'cancelled')
                  AND (
                    :environment = 'all'
                    OR agent_environment.environment = :environment
                  )
                GROUP BY 1
            ),
            requested_buckets AS (
                SELECT generate_series(
                    date_trunc(:bucket, CAST(:start AS timestamptz), 'UTC'),
                    date_trunc(
                        :bucket,
                        CAST(:end AS timestamptz) - interval '1 microsecond',
                        'UTC'
                    ),
                    CAST(:step AS interval)
                ) AS bucket_start
            )
            SELECT
                requested_buckets.bucket_start,
                COALESCE(trace_buckets.requests, 0) AS requests,
                COALESCE(trace_buckets.success, 0) AS success,
                COALESCE(trace_buckets.failed, 0) AS failed,
                trace_buckets.avg_latency_ms,
                trace_buckets.p95_latency_ms,
                COALESCE(trace_buckets.input_tokens, 0) AS input_tokens,
                COALESCE(trace_buckets.output_tokens, 0) AS output_tokens,
                trace_buckets.known_cost_usd,
                COALESCE(trace_buckets.known_cost_count, 0) AS known_cost_count,
                COALESCE(trace_buckets.unknown_cost_count, 0) AS unknown_cost_count
            FROM requested_buckets
            LEFT JOIN trace_buckets USING (bucket_start)
            ORDER BY requested_buckets.bucket_start
            """
        )
        rows = (await session.execute(statement, params)).mappings().all()
        points: list[dict[str, Any]] = []
        for row in rows:
            requests = int(row["requests"] or 0)
            known_cost_count = int(row["known_cost_count"] or 0)
            if requests == 0:
                cost: float | None = 0.0
            elif known_cost_count == 0:
                cost = None
            else:
                cost = round(float(row["known_cost_usd"] or 0), 8)
            points.append(
                {
                    "bucket_start": row["bucket_start"],
                    "requests": requests,
                    "success": int(row["success"] or 0),
                    "failed": int(row["failed"] or 0),
                    "avg_latency_ms": self._rounded(row["avg_latency_ms"]),
                    "p95_latency_ms": self._rounded(row["p95_latency_ms"]),
                    "input_tokens": int(row["input_tokens"] or 0),
                    "output_tokens": int(row["output_tokens"] or 0),
                    "cost_usd": cost,
                    "unknown_cost_count": int(row["unknown_cost_count"] or 0),
                }
            )
        return points

    @staticmethod
    def _agent_environment_cte() -> str:
        return """
        current_release AS (
            SELECT DISTINCT ON (release.agent_id)
                release.agent_id,
                release.status AS environment
            FROM agent.agent_releases AS release
            WHERE release.project_id = :project_id
              AND release.status IN ('production', 'staging', 'draft')
            ORDER BY
                release.agent_id,
                CASE release.status
                    WHEN 'production' THEN 3
                    WHEN 'staging' THEN 2
                    ELSE 1
                END DESC,
                COALESCE(release.promoted_at, release.updated_at, release.created_at) DESC,
                release.created_at DESC,
                release.id DESC
        ),
        agent_environment AS (
            SELECT
                agent.id AS agent_id,
                agent.name AS agent_name,
                agent.status AS agent_status,
                COALESCE(current_release.environment, 'draft') AS environment
            FROM agent.agents AS agent
            LEFT JOIN current_release ON current_release.agent_id = agent.id
            WHERE agent.project_id = :project_id
        )
        """
