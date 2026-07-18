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
from modules.core.infra.database.uow_project_overview_reader import (
    UnitOfWorkProjectOverviewReader,
)
from shared.infra.errors import NotFoundError


class ActiveDocumentProjectOverviewReader(UnitOfWorkProjectOverviewReader):
    """Operational Overview reader with Run-oriented aggregation."""

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
        if not summary.pop("project_exists"):
            raise NotFoundError("Project not found")

        distribution = await self._environment_distribution(session, params)
        summary.update(await self._agent_run_summary(session, params))
        summary.update(await self._network_summary(session, params))

        return {
            "summary": summary,
            "timeseries": await self._run_timeseries(session, params),
            "environment_distribution": distribution,
            "recent_releases": await self._recent_agent_releases(session, params),
            "recent_network_releases": await self._recent_network_releases(
                session,
                params,
            ),
            "recent_traces": await self._recent_direct_agent_runs(session, params),
            "recent_network_runs": await self._recent_network_runs(session, params),
            "operational_issues": await self._operational_issues(session, params),
            "knowledge_summary": await self._knowledge_summary(session, params),
            "tools_summary": await self._tools_summary(session, params),
            "capabilities": {
                "sessions_jobs": False,
                "ingestion_pipeline": False,
                "activity_feed": False,
            },
        }

    @staticmethod
    def _agent_run_context_cte() -> str:
        return """
        current_agent_release AS (
            SELECT DISTINCT ON (release.agent_id)
                release.agent_id,
                release.status AS environment
            FROM agent.agent_releases AS release
            WHERE release.project_id = :project_id
              AND release.status IN ('draft', 'staging', 'production')
            ORDER BY
                release.agent_id,
                CASE release.status
                    WHEN 'production' THEN 3
                    WHEN 'staging' THEN 2
                    ELSE 1
                END DESC,
                COALESCE(release.promoted_at, release.updated_at, release.created_at) DESC,
                release.id DESC
        ),
        agent_run_context AS (
            SELECT
                trace.*,
                agent.name AS agent_name,
                CASE
                    WHEN network_session.environment IN ('draft', 'staging', 'production')
                    THEN network_session.environment
                    WHEN COALESCE(
                        NULLIF(trace.data ->> 'execution_context', ''),
                        NULLIF(trace.data -> 'diagnostics' ->> 'execution_context', '')
                    ) IN ('staging', 'production')
                    THEN COALESCE(
                        NULLIF(trace.data ->> 'execution_context', ''),
                        NULLIF(trace.data -> 'diagnostics' ->> 'execution_context', '')
                    )
                    WHEN COALESCE(
                        NULLIF(trace.data ->> 'execution_context', ''),
                        NULLIF(trace.data -> 'diagnostics' ->> 'execution_context', '')
                    ) = 'playground'
                    THEN 'draft'
                    ELSE COALESCE(current_agent_release.environment, 'draft')
                END AS run_environment,
                CASE
                    WHEN trace.network_execution_id IS NOT NULL THEN 'network'
                    WHEN COALESCE(
                        NULLIF(trace.data ->> 'run_source', ''),
                        NULLIF(trace.data ->> 'source', ''),
                        NULLIF(trace.data ->> 'execution_context', '')
                    ) = 'playground'
                    THEN 'playground'
                    WHEN COALESCE(
                        NULLIF(trace.data ->> 'run_source', ''),
                        NULLIF(trace.data ->> 'source', '')
                    ) IN ('job', 'event', 'schedule')
                    THEN COALESCE(
                        NULLIF(trace.data ->> 'run_source', ''),
                        NULLIF(trace.data ->> 'source', '')
                    )
                    ELSE 'api'
                END AS run_source,
                (
                    trace.status = 'failed'
                    AND (
                        LOWER(COALESCE(trace.error, '')) LIKE '%timeout%'
                        OR LOWER(COALESCE(trace.data ->> 'failure_code', ''))
                            IN ('timeout', 'timed_out', 'provider_timeout')
                        OR LOWER(COALESCE(trace.data ->> 'error_code', ''))
                            LIKE '%timeout%'
                    )
                ) AS is_timeout
            FROM observability.traces AS trace
            LEFT JOIN agent.agents AS agent
              ON agent.id = trace.agent_id
             AND agent.project_id = trace.project_id
            LEFT JOIN current_agent_release
              ON current_agent_release.agent_id = trace.agent_id
            LEFT JOIN network.network_executions AS network_execution
              ON network_execution.id = trace.network_execution_id
            LEFT JOIN network.network_sessions AS network_session
              ON network_session.id = network_execution.network_session_id
            WHERE trace.project_id = :project_id
        )
        """

    async def _agent_run_summary(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> dict[str, int | float | None]:
        statement = text(
            f"""
            WITH {self._agent_run_context_cte()},
            current_runs AS (
                SELECT *
                FROM agent_run_context
                WHERE started_at >= :start
                  AND started_at < :end
                  AND (
                    :environment = 'all'
                    OR run_environment = :environment
                  )
            ),
            previous_runs AS (
                SELECT id
                FROM agent_run_context
                WHERE started_at >= :previous_start
                  AND started_at < :start
                  AND (
                    :environment = 'all'
                    OR run_environment = :environment
                  )
            )
            SELECT
                COUNT(*) AS agent_runs,
                COUNT(*) FILTER (WHERE network_execution_id IS NULL) AS direct_agent_runs,
                COUNT(*) FILTER (WHERE network_execution_id IS NOT NULL) AS network_agent_runs,
                COUNT(*) FILTER (WHERE status IN ('pending', 'queued', 'running', 'processing')) AS running_agent_runs,
                COUNT(*) FILTER (WHERE status = 'completed') AS successful_agent_runs,
                COUNT(*) FILTER (WHERE status = 'failed' AND NOT is_timeout) AS failed_agent_runs,
                COUNT(*) FILTER (WHERE status = 'failed' AND is_timeout) AS timed_out_agent_runs,
                COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_agent_runs,
                COUNT(*) FILTER (WHERE status IN ('completed', 'failed', 'cancelled')) AS terminal_agent_runs,
                AVG(total_latency_ms) FILTER (
                    WHERE status IN ('completed', 'failed', 'cancelled')
                      AND total_latency_ms IS NOT NULL
                ) AS avg_agent_run_duration_ms,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY total_latency_ms) FILTER (
                    WHERE status IN ('completed', 'failed', 'cancelled')
                      AND total_latency_ms IS NOT NULL
                ) AS p95_agent_run_duration_ms,
                SUM(total_cost_usd) FILTER (
                    WHERE status IN ('completed', 'failed', 'cancelled')
                      AND total_cost_usd IS NOT NULL
                ) AS known_cost_usd,
                COUNT(*) FILTER (
                    WHERE status IN ('completed', 'failed', 'cancelled')
                      AND total_cost_usd IS NOT NULL
                ) AS priced_agent_runs,
                COUNT(*) FILTER (
                    WHERE status IN ('completed', 'failed', 'cancelled')
                      AND total_cost_usd IS NULL
                ) AS unknown_cost_count,
                (SELECT COUNT(*) FROM previous_runs) AS previous_agent_runs
            FROM current_runs
            """
        )
        row = (await session.execute(statement, params)).mappings().one()
        total = int(row["agent_runs"] or 0)
        previous = int(row["previous_agent_runs"] or 0)
        terminal = int(row["terminal_agent_runs"] or 0)
        successful = int(row["successful_agent_runs"] or 0)
        failed = int(row["failed_agent_runs"] or 0)
        timed_out = int(row["timed_out_agent_runs"] or 0)
        priced = int(row["priced_agent_runs"] or 0)
        unknown = int(row["unknown_cost_count"] or 0)

        if previous:
            change: float | None = round(((total - previous) / previous) * 100, 2)
        elif total == 0:
            change = 0.0
        else:
            change = None

        if terminal == 0:
            cost: float | None = 0.0
        elif priced == 0:
            cost = None
        else:
            cost = round(float(row["known_cost_usd"] or 0), 8)

        success_rate = round((successful / terminal) * 100, 2) if terminal else None
        error_rate = (
            round(((failed + timed_out) / terminal) * 100, 2)
            if terminal
            else None
        )

        return {
            "agent_runs": total,
            "direct_agent_runs": int(row["direct_agent_runs"] or 0),
            "network_agent_runs": int(row["network_agent_runs"] or 0),
            "terminal_agent_runs": terminal,
            "successful_agent_runs": successful,
            "completed_with_issues_agent_runs": 0,
            "failed_agent_runs": failed,
            "timed_out_agent_runs": timed_out,
            "cancelled_agent_runs": int(row["cancelled_agent_runs"] or 0),
            "running_agent_runs": int(row["running_agent_runs"] or 0),
            "agent_run_change_percent": change,
            "avg_agent_run_duration_ms": self._rounded(
                row["avg_agent_run_duration_ms"]
            ),
            "p95_agent_run_duration_ms": self._rounded(
                row["p95_agent_run_duration_ms"]
            ),
            "agent_run_success_rate": success_rate,
            "agent_run_error_rate": error_rate,
            "agent_run_cost_usd": cost,
            "priced_agent_runs": priced,
            "unknown_agent_run_cost_count": unknown,
            # Transitional compatibility.
            "requests": total,
            "request_change_percent": change,
            "avg_latency_ms": self._rounded(row["avg_agent_run_duration_ms"]),
            "p95_latency_ms": self._rounded(row["p95_agent_run_duration_ms"]),
            "success_rate": success_rate,
            "failed_requests": failed + timed_out,
            "cost_usd": cost,
            "unknown_cost_count": unknown,
        }

    async def _network_summary(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> dict[str, int | float | None]:
        statement = text(
            """
            WITH filtered_executions AS (
                SELECT execution.*
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
            ),
            invocation_totals AS (
                SELECT
                    invocation.network_execution_id,
                    COUNT(*) AS agent_runs
                FROM network.network_invocations AS invocation
                JOIN filtered_executions AS execution
                  ON execution.id = invocation.network_execution_id
                GROUP BY invocation.network_execution_id
            )
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
                COUNT(*) AS network_runs,
                COUNT(*) FILTER (WHERE execution.status = 'completed') AS successful_network_runs,
                COUNT(*) FILTER (WHERE execution.status = 'failed') AS failed_network_runs,
                COUNT(*) FILTER (WHERE execution.status = 'timed_out') AS timed_out_network_runs,
                COUNT(*) FILTER (WHERE execution.status = 'uncertain') AS uncertain_network_runs,
                COUNT(*) FILTER (WHERE execution.status = 'cancelled') AS cancelled_network_runs,
                COUNT(*) FILTER (
                    WHERE execution.status IN ('queued', 'running', 'cancel_requested')
                ) AS running_network_runs,
                COUNT(*) FILTER (
                    WHERE execution.status IN ('completed', 'failed', 'timed_out', 'uncertain', 'cancelled')
                ) AS terminal_network_runs,
                AVG(
                    EXTRACT(EPOCH FROM (execution.completed_at - execution.started_at)) * 1000
                ) FILTER (
                    WHERE execution.started_at IS NOT NULL
                      AND execution.completed_at IS NOT NULL
                ) AS avg_network_run_duration_ms,
                percentile_cont(0.95) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (execution.completed_at - execution.started_at)) * 1000
                ) FILTER (
                    WHERE execution.started_at IS NOT NULL
                      AND execution.completed_at IS NOT NULL
                ) AS p95_network_run_duration_ms,
                AVG(COALESCE(invocation_totals.agent_runs, 0)) FILTER (
                    WHERE execution.status NOT IN ('queued', 'cancel_requested')
                ) AS avg_agent_runs_per_network_run
            FROM filtered_executions AS execution
            LEFT JOIN invocation_totals
              ON invocation_totals.network_execution_id = execution.id
            """
        )
        row = (await session.execute(statement, params)).mappings().one()
        terminal = int(row["terminal_network_runs"] or 0)
        successful = int(row["successful_network_runs"] or 0)
        failed = int(row["failed_network_runs"] or 0)
        timed_out = int(row["timed_out_network_runs"] or 0)
        uncertain = int(row["uncertain_network_runs"] or 0)
        success_rate = round((successful / terminal) * 100, 2) if terminal else None
        error_rate = (
            round(((failed + timed_out + uncertain) / terminal) * 100, 2)
            if terminal
            else None
        )
        return {
            "network_count": int(row["network_count"] or 0),
            "staging_networks": int(row["staging_networks"] or 0),
            "production_networks": int(row["production_networks"] or 0),
            "network_runs": int(row["network_runs"] or 0),
            "terminal_network_runs": terminal,
            "successful_network_runs": successful,
            "completed_with_issues_network_runs": 0,
            "failed_network_runs": failed,
            "timed_out_network_runs": timed_out,
            "uncertain_network_runs": uncertain,
            "cancelled_network_runs": int(row["cancelled_network_runs"] or 0),
            "running_network_runs": int(row["running_network_runs"] or 0),
            "network_run_success_rate": success_rate,
            "network_run_error_rate": error_rate,
            "avg_network_run_duration_ms": self._rounded(
                row["avg_network_run_duration_ms"]
            ),
            "p95_network_run_duration_ms": self._rounded(
                row["p95_network_run_duration_ms"]
            ),
            "avg_agent_runs_per_network_run": self._rounded(
                row["avg_agent_runs_per_network_run"]
            ),
        }

    async def _run_timeseries(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        statement = text(
            f"""
            WITH {self._agent_run_context_cte()},
            agent_buckets AS (
                SELECT
                    date_trunc(:bucket, started_at, 'UTC') AS bucket_start,
                    COUNT(*) AS agent_runs,
                    COUNT(*) FILTER (WHERE status = 'completed') AS agent_run_success,
                    COUNT(*) FILTER (WHERE status = 'failed' AND NOT is_timeout) AS agent_run_failed,
                    COUNT(*) FILTER (WHERE status = 'failed' AND is_timeout) AS agent_run_timed_out,
                    COUNT(*) FILTER (WHERE status = 'cancelled') AS agent_run_cancelled,
                    COUNT(*) FILTER (WHERE status IN ('pending', 'queued', 'running', 'processing')) AS agent_run_running,
                    COUNT(*) FILTER (WHERE status IN ('completed', 'failed', 'cancelled')) AS terminal_agent_runs,
                    AVG(total_latency_ms) FILTER (
                        WHERE status IN ('completed', 'failed', 'cancelled')
                          AND total_latency_ms IS NOT NULL
                    ) AS avg_agent_run_duration_ms,
                    percentile_cont(0.95) WITHIN GROUP (ORDER BY total_latency_ms) FILTER (
                        WHERE status IN ('completed', 'failed', 'cancelled')
                          AND total_latency_ms IS NOT NULL
                    ) AS p95_agent_run_duration_ms,
                    SUM(
                        CASE
                            WHEN COALESCE(data ->> 'input_tokens', '') ~ '^[0-9]+$'
                            THEN (data ->> 'input_tokens')::bigint
                            ELSE 0
                        END
                    ) AS input_tokens,
                    SUM(
                        CASE
                            WHEN COALESCE(data ->> 'output_tokens', '') ~ '^[0-9]+$'
                            THEN (data ->> 'output_tokens')::bigint
                            ELSE 0
                        END
                    ) AS output_tokens,
                    SUM(total_cost_usd) FILTER (
                        WHERE status IN ('completed', 'failed', 'cancelled')
                          AND total_cost_usd IS NOT NULL
                    ) AS known_cost_usd,
                    COUNT(*) FILTER (
                        WHERE status IN ('completed', 'failed', 'cancelled')
                          AND total_cost_usd IS NOT NULL
                    ) AS known_cost_count,
                    COUNT(*) FILTER (
                        WHERE status IN ('completed', 'failed', 'cancelled')
                          AND total_cost_usd IS NULL
                    ) AS unknown_cost_count
                FROM agent_run_context
                WHERE started_at >= :start
                  AND started_at < :end
                  AND (
                    :environment = 'all'
                    OR run_environment = :environment
                  )
                GROUP BY 1
            ),
            network_buckets AS (
                SELECT
                    date_trunc(:bucket, execution.created_at, 'UTC') AS bucket_start,
                    COUNT(*) AS network_runs,
                    COUNT(*) FILTER (WHERE execution.status = 'completed') AS network_run_success,
                    COUNT(*) FILTER (WHERE execution.status = 'failed') AS network_run_failed,
                    COUNT(*) FILTER (WHERE execution.status = 'timed_out') AS network_run_timed_out,
                    COUNT(*) FILTER (WHERE execution.status = 'uncertain') AS network_run_uncertain,
                    COUNT(*) FILTER (WHERE execution.status = 'cancelled') AS network_run_cancelled,
                    COUNT(*) FILTER (
                        WHERE execution.status IN ('queued', 'running', 'cancel_requested')
                    ) AS network_run_running,
                    COUNT(*) FILTER (
                        WHERE execution.status IN ('completed', 'failed', 'timed_out', 'uncertain', 'cancelled')
                    ) AS terminal_network_runs,
                    AVG(
                        EXTRACT(EPOCH FROM (execution.completed_at - execution.started_at)) * 1000
                    ) FILTER (
                        WHERE execution.started_at IS NOT NULL
                          AND execution.completed_at IS NOT NULL
                    ) AS avg_network_run_duration_ms
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
                COALESCE(agent_buckets.agent_runs, 0) AS agent_runs,
                COALESCE(agent_buckets.agent_run_success, 0) AS agent_run_success,
                COALESCE(agent_buckets.agent_run_failed, 0) AS agent_run_failed,
                COALESCE(agent_buckets.agent_run_timed_out, 0) AS agent_run_timed_out,
                COALESCE(agent_buckets.agent_run_cancelled, 0) AS agent_run_cancelled,
                COALESCE(agent_buckets.agent_run_running, 0) AS agent_run_running,
                COALESCE(agent_buckets.terminal_agent_runs, 0) AS terminal_agent_runs,
                agent_buckets.avg_agent_run_duration_ms,
                agent_buckets.p95_agent_run_duration_ms,
                COALESCE(agent_buckets.input_tokens, 0) AS input_tokens,
                COALESCE(agent_buckets.output_tokens, 0) AS output_tokens,
                agent_buckets.known_cost_usd,
                COALESCE(agent_buckets.known_cost_count, 0) AS known_cost_count,
                COALESCE(agent_buckets.unknown_cost_count, 0) AS unknown_cost_count,
                COALESCE(network_buckets.network_runs, 0) AS network_runs,
                COALESCE(network_buckets.network_run_success, 0) AS network_run_success,
                COALESCE(network_buckets.network_run_failed, 0) AS network_run_failed,
                COALESCE(network_buckets.network_run_timed_out, 0) AS network_run_timed_out,
                COALESCE(network_buckets.network_run_uncertain, 0) AS network_run_uncertain,
                COALESCE(network_buckets.network_run_cancelled, 0) AS network_run_cancelled,
                COALESCE(network_buckets.network_run_running, 0) AS network_run_running,
                COALESCE(network_buckets.terminal_network_runs, 0) AS terminal_network_runs,
                network_buckets.avg_network_run_duration_ms
            FROM requested_buckets
            LEFT JOIN agent_buckets USING (bucket_start)
            LEFT JOIN network_buckets USING (bucket_start)
            ORDER BY requested_buckets.bucket_start
            """
        )
        rows = (await session.execute(statement, params)).mappings().all()
        points: list[dict[str, Any]] = []
        for row in rows:
            agent_runs = int(row["agent_runs"] or 0)
            agent_success = int(row["agent_run_success"] or 0)
            agent_failed = int(row["agent_run_failed"] or 0)
            agent_timed_out = int(row["agent_run_timed_out"] or 0)
            agent_terminal = int(row["terminal_agent_runs"] or 0)
            network_success = int(row["network_run_success"] or 0)
            network_terminal = int(row["terminal_network_runs"] or 0)
            known_cost_count = int(row["known_cost_count"] or 0)
            unknown_cost_count = int(row["unknown_cost_count"] or 0)

            if agent_terminal == 0:
                cost: float | None = 0.0
            elif known_cost_count == 0:
                cost = None
            else:
                cost = round(float(row["known_cost_usd"] or 0), 8)

            points.append(
                {
                    "bucket_start": row["bucket_start"],
                    "agent_runs": agent_runs,
                    "agent_run_success": agent_success,
                    "agent_run_completed_with_issues": 0,
                    "agent_run_failed": agent_failed,
                    "agent_run_timed_out": agent_timed_out,
                    "agent_run_cancelled": int(row["agent_run_cancelled"] or 0),
                    "agent_run_running": int(row["agent_run_running"] or 0),
                    "agent_run_success_rate": (
                        round((agent_success / agent_terminal) * 100, 2)
                        if agent_terminal
                        else None
                    ),
                    "avg_agent_run_duration_ms": self._rounded(
                        row["avg_agent_run_duration_ms"]
                    ),
                    "p95_agent_run_duration_ms": self._rounded(
                        row["p95_agent_run_duration_ms"]
                    ),
                    "network_runs": int(row["network_runs"] or 0),
                    "network_run_success": network_success,
                    "network_run_completed_with_issues": 0,
                    "network_run_failed": int(row["network_run_failed"] or 0),
                    "network_run_timed_out": int(
                        row["network_run_timed_out"] or 0
                    ),
                    "network_run_uncertain": int(
                        row["network_run_uncertain"] or 0
                    ),
                    "network_run_cancelled": int(
                        row["network_run_cancelled"] or 0
                    ),
                    "network_run_running": int(row["network_run_running"] or 0),
                    "network_run_success_rate": (
                        round((network_success / network_terminal) * 100, 2)
                        if network_terminal
                        else None
                    ),
                    "avg_network_run_duration_ms": self._rounded(
                        row["avg_network_run_duration_ms"]
                    ),
                    "input_tokens": int(row["input_tokens"] or 0),
                    "output_tokens": int(row["output_tokens"] or 0),
                    "cost_usd": cost,
                    "unknown_cost_count": unknown_cost_count,
                    # Transitional compatibility.
                    "requests": agent_runs,
                    "success": agent_success,
                    "failed": agent_failed + agent_timed_out,
                    "avg_latency_ms": self._rounded(
                        row["avg_agent_run_duration_ms"]
                    ),
                    "p95_latency_ms": self._rounded(
                        row["p95_agent_run_duration_ms"]
                    ),
                }
            )
        return points

    async def _recent_agent_releases(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        statement = text(
            """
            SELECT
                release.id,
                release.agent_id,
                agent.name AS agent_name,
                release.version,
                release.status AS environment,
                release.release_notes,
                release.created_at,
                release.promoted_at
            FROM agent.agent_releases AS release
            JOIN agent.agents AS agent
              ON agent.id = release.agent_id
             AND agent.project_id = :project_id
            WHERE release.project_id = :project_id
              AND release.status IN ('staging', 'production')
              AND COALESCE(release.promoted_at, release.created_at) >= :start
              AND COALESCE(release.promoted_at, release.created_at) < :end
              AND (
                :environment = 'all'
                OR release.status = :environment
              )
            ORDER BY
                COALESCE(release.promoted_at, release.created_at) DESC,
                release.id DESC
            LIMIT :recent_limit
            """
        )
        return [
            dict(row)
            for row in (await session.execute(statement, params)).mappings().all()
        ]

    async def _recent_network_releases(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        statement = text(
            """
            SELECT
                version.id,
                version.network_id,
                network.name AS network_name,
                version.version,
                CASE version.kind
                    WHEN 'release' THEN 'production'
                    ELSE 'staging'
                END AS environment,
                version.change_description,
                version.activation_kind,
                version.rollback_of_version_id,
                CASE
                    WHEN jsonb_typeof(version.definition -> 'nodes') = 'array'
                    THEN jsonb_array_length(version.definition -> 'nodes')
                    ELSE 0
                END AS agent_count,
                version.created_at
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
            ORDER BY version.created_at DESC, version.id DESC
            LIMIT :recent_limit
            """
        )
        return [
            dict(row)
            for row in (await session.execute(statement, params)).mappings().all()
        ]

    async def _recent_direct_agent_runs(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        statement = text(
            f"""
            WITH {self._agent_run_context_cte()}
            SELECT
                id,
                agent_id,
                agent_name,
                run_environment AS environment,
                run_source AS source,
                status,
                total_latency_ms AS latency_ms,
                CASE
                    WHEN COALESCE(data ->> 'total_tokens', '') ~ '^[0-9]+$'
                    THEN (data ->> 'total_tokens')::bigint
                    ELSE NULL
                END AS total_tokens,
                total_cost_usd AS cost_usd,
                total_cost_usd IS NOT NULL AS cost_known,
                started_at
            FROM agent_run_context
            WHERE network_execution_id IS NULL
              AND started_at >= :start
              AND started_at < :end
              AND status IN ('completed', 'failed', 'cancelled')
              AND (
                :environment = 'all'
                OR run_environment = :environment
              )
            ORDER BY started_at DESC NULLS LAST, created_at DESC
            LIMIT :recent_limit
            """
        )
        return [
            dict(row)
            for row in (await session.execute(statement, params)).mappings().all()
        ]

    async def _recent_network_runs(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        statement = text(
            """
            WITH selected_runs AS (
                SELECT
                    execution.id,
                    execution.network_id,
                    network.name AS network_name,
                    network_session.environment,
                    execution.status,
                    execution.root_trace_id,
                    execution.started_at,
                    execution.completed_at,
                    execution.created_at
                FROM network.network_executions AS execution
                JOIN network.network_sessions AS network_session
                  ON network_session.id = execution.network_session_id
                JOIN network.networks AS network
                  ON network.id = execution.network_id
                WHERE execution.project_id = :project_id
                  AND execution.created_at >= :start
                  AND execution.created_at < :end
                  AND (
                    :environment = 'all'
                    OR network_session.environment = :environment
                  )
                ORDER BY execution.created_at DESC, execution.id DESC
                LIMIT :recent_limit
            ),
            execution_costs AS (
                SELECT
                    selected_runs.id AS network_execution_id,
                    COUNT(trace.id) AS total_agent_runs,
                    COUNT(trace.id) FILTER (
                        WHERE trace.total_cost_usd IS NOT NULL
                    ) AS priced_agent_runs,
                    SUM(trace.total_cost_usd) FILTER (
                        WHERE trace.total_cost_usd IS NOT NULL
                    ) AS known_cost_usd
                FROM selected_runs
                LEFT JOIN observability.traces AS trace
                  ON trace.network_execution_id = selected_runs.id
                GROUP BY selected_runs.id
            )
            SELECT
                selected_runs.id,
                selected_runs.network_id,
                selected_runs.network_name,
                selected_runs.environment,
                selected_runs.status,
                CASE
                    WHEN selected_runs.started_at IS NOT NULL
                     AND selected_runs.completed_at IS NOT NULL
                    THEN EXTRACT(
                        EPOCH FROM (
                            selected_runs.completed_at - selected_runs.started_at
                        )
                    ) * 1000
                    ELSE NULL
                END AS duration_ms,
                CASE
                    WHEN execution_costs.priced_agent_runs = 0 THEN NULL
                    ELSE execution_costs.known_cost_usd
                END AS cost_usd,
                (
                    execution_costs.total_agent_runs > 0
                    AND execution_costs.total_agent_runs = execution_costs.priced_agent_runs
                ) AS cost_known,
                COALESCE(execution_costs.priced_agent_runs, 0) AS priced_agent_runs,
                COALESCE(execution_costs.total_agent_runs, 0) AS total_agent_runs,
                GREATEST(
                    COALESCE(execution_costs.total_agent_runs, 0)
                    - COALESCE(execution_costs.priced_agent_runs, 0),
                    0
                ) AS unknown_cost_count,
                selected_runs.root_trace_id,
                selected_runs.started_at,
                selected_runs.completed_at
            FROM selected_runs
            LEFT JOIN execution_costs
              ON execution_costs.network_execution_id = selected_runs.id
            ORDER BY selected_runs.created_at DESC, selected_runs.id DESC
            """
        )
        rows = (await session.execute(statement, params)).mappings().all()
        return [
            {
                **dict(row),
                "duration_ms": self._rounded(row["duration_ms"]),
                "cost_usd": (
                    round(float(row["cost_usd"]), 8)
                    if row["cost_usd"] is not None
                    else None
                ),
            }
            for row in rows
        ]

    async def _operational_issues(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        statement = text(
            f"""
            WITH {self._agent_run_context_cte()},
            agent_failures AS (
                SELECT
                    agent_id AS entity_id,
                    COALESCE(agent_name, 'Unknown Agent') AS name,
                    CASE
                        WHEN is_timeout THEN 'timeout'
                        ELSE COALESCE(
                            NULLIF(data ->> 'failure_code', ''),
                            NULLIF(data ->> 'error_code', ''),
                            'agent_execution_failed'
                        )
                    END AS failure_code,
                    date_trunc(:bucket, started_at, 'UTC') AS bucket_start
                FROM agent_run_context
                WHERE status = 'failed'
                  AND started_at >= :start
                  AND started_at < :end
                  AND (
                    :environment = 'all'
                    OR run_environment = :environment
                  )
            ),
            network_failures AS (
                SELECT
                    execution.network_id AS entity_id,
                    network.name,
                    COALESCE(
                        NULLIF(execution.failure_code, ''),
                        execution.status
                    ) AS failure_code,
                    date_trunc(:bucket, execution.created_at, 'UTC') AS bucket_start
                FROM network.network_executions AS execution
                JOIN network.network_sessions AS network_session
                  ON network_session.id = execution.network_session_id
                JOIN network.networks AS network
                  ON network.id = execution.network_id
                WHERE execution.project_id = :project_id
                  AND execution.status IN ('failed', 'timed_out', 'uncertain')
                  AND execution.created_at >= :start
                  AND execution.created_at < :end
                  AND (
                    :environment = 'all'
                    OR network_session.environment = :environment
                  )
            ),
            top_agent AS (
                SELECT entity_id, name, COUNT(*) AS failure_count
                FROM agent_failures
                GROUP BY entity_id, name
                ORDER BY failure_count DESC, name
                LIMIT 3
            ),
            top_network AS (
                SELECT entity_id, name, COUNT(*) AS failure_count
                FROM network_failures
                GROUP BY entity_id, name
                ORDER BY failure_count DESC, name
                LIMIT 3
            ),
            all_failure_codes AS (
                SELECT failure_code FROM agent_failures
                UNION ALL
                SELECT failure_code FROM network_failures
            ),
            top_codes AS (
                SELECT failure_code AS code, COUNT(*) AS failure_count
                FROM all_failure_codes
                GROUP BY failure_code
                ORDER BY failure_count DESC, failure_code
                LIMIT 5
            ),
            all_failure_buckets AS (
                SELECT bucket_start FROM agent_failures
                UNION ALL
                SELECT bucket_start FROM network_failures
            ),
            peak AS (
                SELECT bucket_start, COUNT(*) AS failure_count
                FROM all_failure_buckets
                GROUP BY bucket_start
                ORDER BY failure_count DESC, bucket_start DESC
                LIMIT 1
            )
            SELECT
                COALESCE(
                    (
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'entity_id', entity_id,
                                'name', name,
                                'failure_count', failure_count
                            )
                            ORDER BY failure_count DESC, name
                        )
                        FROM top_agent
                    ),
                    '[]'::jsonb
                ) AS top_agent_failures,
                COALESCE(
                    (
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'entity_id', entity_id,
                                'name', name,
                                'failure_count', failure_count
                            )
                            ORDER BY failure_count DESC, name
                        )
                        FROM top_network
                    ),
                    '[]'::jsonb
                ) AS top_network_failures,
                COALESCE(
                    (
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'code', code,
                                'failure_count', failure_count
                            )
                            ORDER BY failure_count DESC, code
                        )
                        FROM top_codes
                    ),
                    '[]'::jsonb
                ) AS top_failure_codes,
                (
                    SELECT jsonb_build_object(
                        'bucket_start', bucket_start,
                        'failure_count', failure_count
                    )
                    FROM peak
                ) AS failure_peak
            """
        )
        row = (await session.execute(statement, params)).mappings().one()
        return {
            "top_agent_failures": list(row["top_agent_failures"] or []),
            "top_network_failures": list(row["top_network_failures"] or []),
            "top_failure_codes": list(row["top_failure_codes"] or []),
            "failure_peak": row["failure_peak"],
        }

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
