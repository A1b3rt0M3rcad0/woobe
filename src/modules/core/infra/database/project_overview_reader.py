from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.application.dtos.project_overview import (
    OverviewBucket,
    OverviewEnvironment,
)
from shared.infra.errors import NotFoundError

_AGENT_ENVIRONMENT_CTE = """
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

_TRACE_ENVIRONMENT_SQL = """
COALESCE(
    NULLIF(trace.data ->> 'execution_context', ''),
    NULLIF(trace.data -> 'diagnostics' ->> 'execution_context', ''),
    agent_environment.environment,
    'draft'
)
"""


class SQLAlchemyProjectOverviewReader:
    """Constant-query cross-schema read model owned by the core query side."""

    query_count = 7

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

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
            "step": "1 hour" if bucket == "hour" else "1 day",
        }
        async with self._session_factory() as session:
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

    async def _summary(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        statement = text(
            f"""
            WITH {_AGENT_ENVIRONMENT_CTE},
            current_traces AS (
                SELECT trace.*
                FROM observability.traces AS trace
                LEFT JOIN agent_environment
                    ON agent_environment.agent_id = trace.agent_id
                WHERE trace.project_id = :project_id
                  AND trace.started_at >= :start
                  AND trace.started_at < :end
                  AND trace.status IN ('completed', 'failed', 'cancelled')
                  AND (
                    :environment = 'all'
                    OR {_TRACE_ENVIRONMENT_SQL} = :environment
                  )
            ),
            previous_traces AS (
                SELECT trace.id
                FROM observability.traces AS trace
                LEFT JOIN agent_environment
                    ON agent_environment.agent_id = trace.agent_id
                WHERE trace.project_id = :project_id
                  AND trace.started_at >= :previous_start
                  AND trace.started_at < :start
                  AND trace.status IN ('completed', 'failed', 'cancelled')
                  AND (
                    :environment = 'all'
                    OR {_TRACE_ENVIRONMENT_SQL} = :environment
                  )
            )
            SELECT
                EXISTS(
                    SELECT 1 FROM core.projects WHERE id = :project_id
                ) AS project_exists,
                (
                    SELECT COUNT(*)
                    FROM agent_environment
                    WHERE agent_status = 'active'
                      AND (
                        :environment = 'all'
                        OR environment = :environment
                      )
                ) AS active_agents,
                (
                    SELECT COUNT(*)
                    FROM agent_environment
                    WHERE environment = 'production'
                ) AS production_agents,
                COUNT(*) AS requests,
                COUNT(*) FILTER (
                    WHERE status = 'completed'
                ) AS successful_requests,
                COUNT(*) FILTER (
                    WHERE status IN ('failed', 'cancelled')
                ) AS failed_requests,
                AVG(total_latency_ms) FILTER (
                    WHERE total_latency_ms IS NOT NULL
                ) AS avg_latency_ms,
                percentile_cont(0.95) WITHIN GROUP (
                    ORDER BY total_latency_ms
                ) FILTER (
                    WHERE total_latency_ms IS NOT NULL
                ) AS p95_latency_ms,
                SUM(total_cost_usd) FILTER (
                    WHERE total_cost_usd IS NOT NULL
                ) AS known_cost_usd,
                COUNT(*) FILTER (
                    WHERE total_cost_usd IS NOT NULL
                ) AS known_cost_count,
                COUNT(*) FILTER (
                    WHERE total_cost_usd IS NULL
                ) AS unknown_cost_count,
                (SELECT COUNT(*) FROM previous_traces) AS previous_requests
            FROM current_traces
            """
        )
        row = (await session.execute(statement, params)).mappings().one()
        requests = int(row["requests"] or 0)
        successes = int(row["successful_requests"] or 0)
        previous_requests = int(row["previous_requests"] or 0)
        known_cost_count = int(row["known_cost_count"] or 0)

        if previous_requests:
            change = round(
                ((requests - previous_requests) / previous_requests) * 100,
                2,
            )
        elif requests == 0:
            change = 0.0
        else:
            change = None

        if requests == 0:
            cost_usd: float | None = 0.0
        elif known_cost_count == 0:
            cost_usd = None
        else:
            cost_usd = round(float(row["known_cost_usd"] or 0), 8)

        return {
            "project_exists": bool(row["project_exists"]),
            "active_agents": int(row["active_agents"] or 0),
            "production_agents": int(row["production_agents"] or 0),
            "requests": requests,
            "request_change_percent": change,
            "avg_latency_ms": self._rounded(row["avg_latency_ms"]),
            "p95_latency_ms": self._rounded(row["p95_latency_ms"]),
            "success_rate": (
                round((successes / requests) * 100, 2) if requests else None
            ),
            "failed_requests": int(row["failed_requests"] or 0),
            "cost_usd": cost_usd,
            "unknown_cost_count": int(row["unknown_cost_count"] or 0),
        }

    async def _timeseries(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        statement = text(
            f"""
            WITH {_AGENT_ENVIRONMENT_CTE},
            trace_buckets AS (
                SELECT
                    date_trunc(:bucket, trace.started_at) AS bucket_start,
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
                    OR {_TRACE_ENVIRONMENT_SQL} = :environment
                  )
                GROUP BY 1
            ),
            requested_buckets AS (
                SELECT generate_series(
                    date_trunc(:bucket, CAST(:start AS timestamptz)),
                    date_trunc(
                        :bucket,
                        CAST(:end AS timestamptz) - interval '1 microsecond'
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

    async def _environment_distribution(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> dict[str, int]:
        statement = text(
            f"""
            WITH {_AGENT_ENVIRONMENT_CTE}
            SELECT
                COUNT(*) FILTER (WHERE environment = 'draft') AS draft,
                COUNT(*) FILTER (WHERE environment = 'staging') AS staging,
                COUNT(*) FILTER (WHERE environment = 'production') AS production
            FROM agent_environment
            """
        )
        row = (await session.execute(statement, params)).mappings().one()
        return {
            "draft": int(row["draft"] or 0),
            "staging": int(row["staging"] or 0),
            "production": int(row["production"] or 0),
        }

    async def _recent_releases(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        statement = text(
            """
            WITH ranked_releases AS (
                SELECT
                    release.id,
                    release.agent_id,
                    agent.name AS agent_name,
                    release.version,
                    release.status AS environment,
                    release.created_at,
                    release.promoted_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY release.agent_id, release.status
                        ORDER BY
                            COALESCE(release.promoted_at, release.updated_at, release.created_at) DESC,
                            release.created_at DESC,
                            release.id DESC
                    ) AS status_rank
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
            )
            SELECT
                id,
                agent_id,
                agent_name,
                version,
                environment,
                created_at,
                promoted_at
            FROM ranked_releases
            WHERE status_rank = 1
            ORDER BY
                COALESCE(promoted_at, created_at) DESC,
                created_at DESC,
                id DESC
            LIMIT :recent_limit
            """
        )
        return [
            dict(row)
            for row in (await session.execute(statement, params)).mappings().all()
        ]

    async def _recent_traces(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        statement = text(
            f"""
            WITH {_AGENT_ENVIRONMENT_CTE}
            SELECT
                trace.id,
                trace.agent_id,
                agent_environment.agent_name,
                {_TRACE_ENVIRONMENT_SQL} AS environment,
                trace.status,
                trace.total_latency_ms AS latency_ms,
                CASE
                    WHEN COALESCE(trace.data ->> 'total_tokens', '') ~ '^[0-9]+$'
                    THEN (trace.data ->> 'total_tokens')::bigint
                    ELSE NULL
                END AS total_tokens,
                trace.total_cost_usd AS cost_usd,
                trace.total_cost_usd IS NOT NULL AS cost_known,
                trace.started_at
            FROM observability.traces AS trace
            LEFT JOIN agent_environment
                ON agent_environment.agent_id = trace.agent_id
            WHERE trace.project_id = :project_id
              AND trace.started_at >= :start
              AND trace.started_at < :end
              AND trace.status IN ('completed', 'failed', 'cancelled')
              AND (
                :environment = 'all'
                OR {_TRACE_ENVIRONMENT_SQL} = :environment
              )
            ORDER BY trace.started_at DESC NULLS LAST, trace.created_at DESC
            LIMIT :recent_limit
            """
        )
        return [
            dict(row)
            for row in (await session.execute(statement, params)).mappings().all()
        ]

    async def _knowledge_summary(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> dict[str, int]:
        statement = text(
            """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM agent.document_collections
                    WHERE project_id = :project_id
                ) AS collections,
                COUNT(*) AS documents,
                COUNT(*) FILTER (
                    WHERE indexed_at IS NOT NULL OR status = 'indexed'
                ) AS indexed_documents,
                COUNT(*) FILTER (
                    WHERE status IN ('failed', 'error')
                ) AS failed_documents,
                COALESCE(SUM(size_bytes), 0) AS storage_bytes,
                COUNT(*) FILTER (
                    WHERE indexed_at IS NULL
                      AND status NOT IN ('failed', 'error')
                ) AS pending_documents
            FROM agent.documents
            WHERE project_id = :project_id
            """
        )
        row = (await session.execute(statement, params)).mappings().one()
        return {key: int(row[key] or 0) for key in row.keys()}

    async def _tools_summary(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        statement = text(
            """
            WITH tool_counts AS (
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'active') AS active,
                    COUNT(*) FILTER (WHERE status <> 'active') AS inactive
                FROM agent.tools
                WHERE project_id = :project_id
            ),
            failures AS (
                SELECT
                    trace_event.trace_id,
                    COALESCE(
                        trace_event.payload ->> 'tool_name',
                        'unknown'
                    ) AS tool_name,
                    trace_event.created_at AS occurred_at
                FROM observability.trace_events AS trace_event
                WHERE trace_event.project_id = :project_id
                  AND trace_event.created_at >= :start
                  AND trace_event.created_at < :end
                  AND trace_event.event_type = 'tool_call'
                  AND (
                    trace_event.payload ->> 'success' = 'false'
                    OR trace_event.payload ->> 'status' = 'error'
                  )
                ORDER BY trace_event.created_at DESC
                LIMIT 5
            )
            SELECT
                tool_counts.total,
                tool_counts.active,
                tool_counts.inactive,
                COALESCE(
                    jsonb_agg(
                        jsonb_build_object(
                            'trace_id', failures.trace_id,
                            'tool_name', failures.tool_name,
                            'occurred_at', failures.occurred_at,
                            'error', NULL
                        )
                        ORDER BY failures.occurred_at DESC
                    ) FILTER (WHERE failures.trace_id IS NOT NULL),
                    '[]'::jsonb
                ) AS recent_failures
            FROM tool_counts
            LEFT JOIN failures ON TRUE
            GROUP BY tool_counts.total, tool_counts.active, tool_counts.inactive
            """
        )
        row = (await session.execute(statement, params)).mappings().one()
        return {
            "total": int(row["total"] or 0),
            "active": int(row["active"] or 0),
            "inactive": int(row["inactive"] or 0),
            "recent_failures": list(row["recent_failures"] or []),
        }

    @staticmethod
    def _rounded(value: Any) -> float | None:
        if value is None:
            return None
        return round(float(value), 3)
