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

        summary = sections["summary"]
        summary.update(await self._agent_run_summary(self._uow.session, params))
        summary.update(await self._network_summary(self._uow.session, params))

        network_series = await self._network_timeseries(self._uow.session, params)
        network_by_bucket = {point["bucket_start"]: point for point in network_series}
        for point in sections["timeseries"]:
            self._apply_agent_run_timeseries_projection(point)
            network_point = network_by_bucket.get(point["bucket_start"])
            point.update(
                network_point
                or {
                    "network_runs": 0,
                    "network_run_success": 0,
                    "network_run_failed": 0,
                    "avg_network_run_duration_ms": None,
                }
            )

        sections["recent_network_runs"] = await self._recent_network_runs(
            self._uow.session,
            params,
        )
        return sections

    async def _agent_run_summary(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> dict[str, int | float | None]:
        statement = text(
            f"""
            WITH {self._agent_environment_cte()},
            current_runs AS (
                SELECT trace.*
                FROM observability.traces AS trace
                LEFT JOIN agent_environment
                  ON agent_environment.agent_id = trace.agent_id
                WHERE trace.project_id = :project_id
                  AND trace.started_at >= :start
                  AND trace.started_at < :end
                  AND (
                    :environment = 'all'
                    OR agent_environment.environment = :environment
                  )
            ),
            previous_runs AS (
                SELECT trace.id
                FROM observability.traces AS trace
                LEFT JOIN agent_environment
                  ON agent_environment.agent_id = trace.agent_id
                WHERE trace.project_id = :project_id
                  AND trace.started_at >= :previous_start
                  AND trace.started_at < :start
                  AND (
                    :environment = 'all'
                    OR agent_environment.environment = :environment
                  )
            )
            SELECT
                COUNT(*) AS agent_runs,
                COUNT(*) FILTER (WHERE network_execution_id IS NULL) AS direct_agent_runs,
                COUNT(*) FILTER (WHERE network_execution_id IS NOT NULL) AS network_agent_runs,
                COUNT(*) FILTER (WHERE status IN ('pending', 'queued', 'running', 'processing')) AS running_agent_runs,
                COUNT(*) FILTER (WHERE status IN ('failed', 'cancelled')) AS failed_agent_runs,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed_agent_runs,
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
                ) AS known_cost_count,
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
        completed = int(row["completed_agent_runs"] or 0)
        known_count = int(row["known_cost_count"] or 0)
        unknown_count = int(row["unknown_cost_count"] or 0)
        if previous:
            change: float | None = round(((total - previous) / previous) * 100, 2)
        elif total == 0:
            change = 0.0
        else:
            change = None
        if terminal == 0:
            cost: float | None = 0.0
        elif known_count == 0:
            cost = None
        else:
            cost = round(float(row["known_cost_usd"] or 0), 8)
        return {
            "agent_runs": total,
            "direct_agent_runs": int(row["direct_agent_runs"] or 0),
            "network_agent_runs": int(row["network_agent_runs"] or 0),
            "running_agent_runs": int(row["running_agent_runs"] or 0),
            "failed_agent_runs": int(row["failed_agent_runs"] or 0),
            "agent_run_change_percent": change,
            "avg_agent_run_duration_ms": self._rounded(row["avg_agent_run_duration_ms"]),
            "p95_agent_run_duration_ms": self._rounded(row["p95_agent_run_duration_ms"]),
            "agent_run_success_rate": round((completed / terminal) * 100, 2) if terminal else None,
            "agent_run_cost_usd": cost,
            "unknown_agent_run_cost_count": unknown_count,
        }

    @staticmethod
    def _apply_agent_run_timeseries_projection(point: dict[str, Any]) -> None:
        point.update(
            {
                "agent_runs": int(point.get("requests") or 0),
                "agent_run_success": int(point.get("success") or 0),
                "agent_run_failed": int(point.get("failed") or 0),
                "avg_agent_run_duration_ms": point.get("avg_latency_ms"),
                "p95_agent_run_duration_ms": point.get("p95_latency_ms"),
            }
        )

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
                COALESCE(SUM(invocation_totals.agent_runs), 0) AS network_agent_runs,
                COUNT(*) FILTER (
                    WHERE execution.status IN ('queued', 'running', 'cancel_requested')
                ) AS running_network_runs,
                COUNT(*) FILTER (
                    WHERE execution.status IN ('failed', 'timed_out', 'uncertain', 'cancelled')
                ) AS failed_network_runs,
                COUNT(*) FILTER (
                    WHERE execution.status = 'completed'
                ) AS completed_network_runs,
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
        completed = int(row["completed_network_runs"] or 0)
        return {
            "network_count": int(row["network_count"] or 0),
            "staging_networks": int(row["staging_networks"] or 0),
            "production_networks": int(row["production_networks"] or 0),
            "network_runs": int(row["network_runs"] or 0),
            "network_agent_runs": int(row["network_agent_runs"] or 0),
            "running_network_runs": int(row["running_network_runs"] or 0),
            "failed_network_runs": int(row["failed_network_runs"] or 0),
            "network_run_success_rate": (
                round((completed / terminal) * 100, 2) if terminal else None
            ),
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

    async def _network_timeseries(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        statement = text(
            """
            SELECT
                date_trunc(:bucket, execution.created_at, 'UTC') AS bucket_start,
                COUNT(*) AS network_runs,
                COUNT(*) FILTER (
                    WHERE execution.status = 'completed'
                ) AS network_run_success,
                COUNT(*) FILTER (
                    WHERE execution.status IN ('failed', 'timed_out', 'uncertain', 'cancelled')
                ) AS network_run_failed,
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
            ORDER BY 1
            """
        )
        rows = (await session.execute(statement, params)).mappings().all()
        return [
            {
                "bucket_start": row["bucket_start"],
                "network_runs": int(row["network_runs"] or 0),
                "network_run_success": int(row["network_run_success"] or 0),
                "network_run_failed": int(row["network_run_failed"] or 0),
                "avg_network_run_duration_ms": self._rounded(
                    row["avg_network_run_duration_ms"]
                ),
            }
            for row in rows
        ]

    async def _recent_network_runs(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        statement = text(
            """
            SELECT
                execution.id,
                execution.network_id,
                network.name AS network_name,
                network_session.environment,
                execution.status,
                CASE
                    WHEN execution.started_at IS NOT NULL
                     AND execution.completed_at IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (execution.completed_at - execution.started_at)) * 1000
                    ELSE NULL
                END AS duration_ms,
                execution.root_trace_id,
                execution.started_at,
                execution.completed_at
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
            """
        )
        rows = (await session.execute(statement, params)).mappings().all()
        return [
            {
                "id": row["id"],
                "network_id": row["network_id"],
                "network_name": row["network_name"],
                "environment": row["environment"],
                "status": row["status"],
                "duration_ms": self._rounded(row["duration_ms"]),
                "root_trace_id": row["root_trace_id"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
            }
            for row in rows
        ]

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
