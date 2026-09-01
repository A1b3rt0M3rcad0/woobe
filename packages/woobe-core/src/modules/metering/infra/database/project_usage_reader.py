from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text

from modules.metering.application.dtos.project_usage import ProjectUsageQuery
from modules.metering.infra.database.unit_of_work import MeteringUnitOfWork
from shared.infra.errors import NotFoundError


_GROUP_SQL: dict[str, tuple[str, str]] = {
    "agent": (
        "COALESCE(filtered.agent_id::text, 'unattributed')",
        "COALESCE(filtered.agent_name, 'Unattributed Agent')",
    ),
    "network": (
        "COALESCE(filtered.network_id::text, 'direct')",
        "COALESCE(filtered.network_name, 'Direct Agent Runs')",
    ),
    "model": (
        "COALESCE(filtered.provider_model_id::text, filtered.model, 'unattributed')",
        "COALESCE(NULLIF(CONCAT_WS(' / ', filtered.provider, filtered.model), ''), 'Unattributed Model')",
    ),
    "provider": (
        "COALESCE(filtered.provider, 'unattributed')",
        "COALESCE(filtered.provider, 'Unattributed Provider')",
    ),
    "environment": (
        "filtered.run_environment",
        "INITCAP(filtered.run_environment)",
    ),
    "release": (
        "COALESCE(filtered.release_id_text, 'unattributed')",
        "COALESCE(filtered.release_version, filtered.release_id_text, 'Unattributed Release')",
    ),
}


class SQLAlchemyProjectUsageReader:
    def __init__(self, uow: MeteringUnitOfWork) -> None:
        self._uow = uow

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
                trace.id AS trace_id,
                trace.project_id,
                trace.network_id,
                network.name AS network_name,
                trace.network_execution_id,
                trace.network_version_id,
                trace.agent_id,
                agent.name AS agent_name,
                trace.status,
                trace.error,
                trace.started_at,
                trace.ended_at,
                trace.total_latency_ms,
                trace.total_cost_usd,
                trace.provider,
                trace.model,
                trace.provider_model_id,
                trace.data,
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
                COALESCE(
                    NULLIF(trace.data ->> 'agent_release_id', ''),
                    NULLIF(trace.data -> 'diagnostics' ->> 'agent_release_id', '')
                ) AS release_id_text,
                COALESCE(
                    NULLIF(trace.data ->> 'agent_release_version', ''),
                    NULLIF(trace.data -> 'diagnostics' ->> 'agent_release_version', '')
                ) AS release_version,
                COALESCE(
                    CASE
                        WHEN COALESCE(trace.data ->> 'llm_call_count', '') ~ '^[0-9]+$'
                        THEN (trace.data ->> 'llm_call_count')::integer
                        WHEN COALESCE(trace.data -> 'diagnostics' ->> 'llm_call_count', '') ~ '^[0-9]+$'
                        THEN (trace.data -> 'diagnostics' ->> 'llm_call_count')::integer
                        WHEN jsonb_typeof(trace.data -> 'llm_calls') = 'array'
                        THEN jsonb_array_length(trace.data -> 'llm_calls')
                        ELSE 0
                    END,
                    0
                ) AS llm_calls,
                COALESCE(
                    CASE
                        WHEN COALESCE(trace.data ->> 'tool_call_count', '') ~ '^[0-9]+$'
                        THEN (trace.data ->> 'tool_call_count')::integer
                        WHEN COALESCE(trace.data -> 'diagnostics' ->> 'tool_call_count', '') ~ '^[0-9]+$'
                        THEN (trace.data -> 'diagnostics' ->> 'tool_call_count')::integer
                        WHEN jsonb_typeof(trace.data -> 'tool_calls') = 'array'
                        THEN jsonb_array_length(trace.data -> 'tool_calls')
                        ELSE 0
                    END,
                    0
                ) AS tool_calls,
                COALESCE(
                    CASE
                        WHEN COALESCE(trace.data ->> 'input_tokens', '') ~ '^[0-9]+$'
                        THEN (trace.data ->> 'input_tokens')::bigint
                        ELSE 0
                    END,
                    0
                ) AS input_tokens,
                COALESCE(
                    CASE
                        WHEN COALESCE(trace.data ->> 'output_tokens', '') ~ '^[0-9]+$'
                        THEN (trace.data ->> 'output_tokens')::bigint
                        ELSE 0
                    END,
                    0
                ) AS output_tokens,
                COALESCE(
                    CASE
                        WHEN COALESCE(trace.data ->> 'embedding_tokens', '') ~ '^[0-9]+$'
                        THEN (trace.data ->> 'embedding_tokens')::bigint
                        ELSE 0
                    END,
                    0
                ) AS embedding_tokens,
                COALESCE(
                    NULLIF(trace.data ->> 'cost_status', ''),
                    NULLIF(trace.data -> 'diagnostics' ->> 'cost_status', ''),
                    CASE WHEN trace.total_cost_usd IS NULL THEN 'unknown' ELSE 'known' END
                ) AS cost_status,
                (
                    trace.status = 'failed'
                    AND (
                        LOWER(COALESCE(trace.error, '')) LIKE '%timeout%'
                        OR LOWER(COALESCE(trace.data ->> 'failure_code', ''))
                            IN ('timeout', 'timed_out', 'provider_timeout')
                        OR LOWER(COALESCE(trace.data ->> 'error_code', '')) LIKE '%timeout%'
                    )
                ) AS is_timeout
            FROM observability.traces AS trace
            LEFT JOIN agent.agents AS agent
              ON agent.id = trace.agent_id
             AND agent.project_id = trace.project_id
            LEFT JOIN network.networks AS network
              ON network.id = trace.network_id
             AND network.project_id = trace.project_id
            LEFT JOIN current_agent_release
              ON current_agent_release.agent_id = trace.agent_id
            LEFT JOIN network.network_executions AS network_execution
              ON network_execution.id = trace.network_execution_id
            LEFT JOIN network.network_sessions AS network_session
              ON network_session.id = network_execution.network_session_id
            WHERE trace.project_id = :project_id
        )
        """

    @staticmethod
    def _agent_scope_sql(alias: str = "run") -> str:
        return f"""
        {alias}.status IN ('completed', 'failed', 'cancelled')
        AND (:environment = 'all' OR {alias}.run_environment = :environment)
        AND (
            :operation = 'all'
            OR (:operation = 'agent' AND {alias}.network_execution_id IS NULL)
            OR (:operation = 'network' AND {alias}.network_execution_id IS NOT NULL)
        )
        AND (CAST(:network_id AS uuid) IS NULL OR {alias}.network_id = CAST(:network_id AS uuid))
        AND (CAST(:agent_id AS uuid) IS NULL OR {alias}.agent_id = CAST(:agent_id AS uuid))
        AND (
            CAST(:provider_model_id AS uuid) IS NULL
            OR {alias}.provider_model_id = CAST(:provider_model_id AS uuid)
            OR {alias}.data ->> 'provider_model_id' = CAST(:provider_model_id AS text)
            OR {alias}.data -> 'diagnostics' ->> 'provider_model_id' = CAST(:provider_model_id AS text)
        )
        AND (
            CAST(:release_id AS uuid) IS NULL
            OR {alias}.release_id_text = CAST(:release_id AS text)
        )
        """

    async def fetch(self, query: ProjectUsageQuery) -> dict[str, Any]:
        assert query.from_ is not None
        assert query.to is not None
        assert query.bucket is not None
        duration = query.to - query.from_
        params: dict[str, Any] = {
            "project_id": query.project_id,
            "start": query.from_,
            "end": query.to,
            "previous_start": query.from_ - duration,
            "environment": query.environment,
            "operation": query.operation,
            "network_id": query.network_id,
            "agent_id": query.agent_id,
            "provider_model_id": query.provider_model_id,
            "release_id": query.release_id,
            "bucket": query.bucket,
            "step": timedelta(hours=1) if query.bucket == "hour" else timedelta(days=1),
            "top_limit": query.top_limit,
        }

        agent_summary = await self._agent_summary(params)
        if not agent_summary.pop("project_exists"):
            raise NotFoundError("Project not found")
        network_summary = await self._network_summary(params)

        summary = {**agent_summary, **network_summary}
        agent_runs = int(summary["agent_runs"])
        priced_agent_runs = int(summary["priced_agent_runs"])
        known_cost = summary["known_cost_usd"]
        input_tokens = int(summary["input_tokens"])
        output_tokens = int(summary["output_tokens"])

        summary["cost_coverage_percent"] = (
            round((priced_agent_runs / agent_runs) * 100, 2) if agent_runs else None
        )
        summary["cost_per_priced_agent_run"] = (
            round(float(known_cost) / priced_agent_runs, 8)
            if known_cost is not None and priced_agent_runs
            else None
        )
        summary["cost_per_priced_request"] = summary["cost_per_priced_agent_run"]
        summary["tokens_per_request"] = (
            round((input_tokens + output_tokens) / agent_runs, 2)
            if agent_runs
            else None
        )

        # Transitional aliases remain exact projections of Agent Runs.
        summary["runtime_requests"] = agent_runs
        summary["successful_requests"] = summary["successful_agent_runs"]
        summary["failed_requests"] = summary["failed_agent_runs"]
        summary["cancelled_requests"] = summary["cancelled_agent_runs"]
        summary["priced_requests"] = priced_agent_runs
        summary["partial_cost_requests"] = summary["partial_cost_agent_runs"]
        summary["unpriced_requests"] = summary["unpriced_agent_runs"]
        summary["request_change_percent"] = summary["agent_run_change_percent"]

        timeseries = await self._timeseries(params)
        breakdown = await self._breakdown(params, query.group_by)
        top_executions = await self._top_executions(params)

        total_cost = float(known_cost or 0)
        for row in breakdown:
            row_cost = float(row.get("known_cost_usd") or 0)
            row["share_percent"] = (
                round((row_cost / total_cost) * 100, 2) if total_cost else 0.0
            )
            priced = int(row.pop("priced_agent_runs", 0))
            runs = int(row["agent_runs"])
            unit_cost = round(row_cost / priced, 8) if priced else None
            coverage = round((priced / runs) * 100, 2) if runs else None
            row["cost_per_priced_agent_run"] = unit_cost
            row["cost_coverage_percent"] = coverage
            row["runtime_requests"] = runs
            row["successful_requests"] = row["successful_agent_runs"]
            row["cost_per_priced_request"] = unit_cost

        data_through = self._latest_timestamp(
            summary.pop("agent_data_through", None),
            summary.pop("network_data_through", None),
        )
        freshness_seconds = None
        if data_through is not None:
            freshness_seconds = max(
                round((datetime.now(UTC) - data_through).total_seconds()),
                0,
            )

        return {
            "project_id": query.project_id,
            "generated_at": datetime.now(UTC),
            "data_through": data_through,
            "from": query.from_,
            "to": query.to,
            "bucket": query.bucket,
            "environment": query.environment,
            "operation": query.operation,
            "group_by": query.group_by,
            "summary": summary,
            "timeseries": timeseries,
            "composition": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "embedding_tokens": int(summary.pop("embedding_tokens")),
                "tool_calls": int(summary.pop("tool_calls")),
                "vector_queries": 0,
            },
            "breakdown": breakdown,
            "top_executions": top_executions,
            "data_quality": {
                "fully_priced_agent_runs": priced_agent_runs,
                "partial_agent_runs": int(summary["partial_cost_agent_runs"]),
                "unpriced_agent_runs": int(summary["unpriced_agent_runs"]),
                "fully_priced_network_runs": int(summary["priced_network_runs"]),
                "partial_network_runs": int(summary["partial_cost_network_runs"]),
                "unpriced_network_runs": int(summary["unpriced_network_runs"]),
                "missing_model_attribution": int(summary.pop("missing_model_attribution")),
                "missing_release_attribution": int(summary.pop("missing_release_attribution")),
                "aggregation_lag_seconds": freshness_seconds,
                "fully_priced_requests": priced_agent_runs,
                "partial_requests": int(summary["partial_cost_agent_runs"]),
                "unpriced_requests": int(summary["unpriced_agent_runs"]),
            },
        }

    async def _agent_summary(self, params: dict[str, Any]) -> dict[str, Any]:
        scope = self._agent_scope_sql()
        statement = text(
            f"""
            WITH {self._agent_run_context_cte()},
            current_runs AS (
                SELECT *
                FROM agent_run_context AS run
                WHERE run.started_at >= :start
                  AND run.started_at < :end
                  AND {scope}
            ),
            previous_runs AS (
                SELECT *
                FROM agent_run_context AS run
                WHERE run.started_at >= :previous_start
                  AND run.started_at < :start
                  AND {scope}
            )
            SELECT
                EXISTS(SELECT 1 FROM core.projects WHERE id = :project_id) AS project_exists,
                COUNT(*) AS agent_runs,
                COUNT(*) FILTER (WHERE network_execution_id IS NULL) AS direct_agent_runs,
                COUNT(*) FILTER (WHERE network_execution_id IS NOT NULL) AS network_agent_runs,
                COUNT(*) FILTER (WHERE status = 'completed') AS successful_agent_runs,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed_agent_runs,
                COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_agent_runs,
                COALESCE(SUM(llm_calls), 0) AS llm_calls,
                COALESCE(SUM(input_tokens), 0) AS input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(embedding_tokens), 0) AS embedding_tokens,
                COALESCE(SUM(tool_calls), 0) AS tool_calls,
                SUM(total_cost_usd) FILTER (WHERE total_cost_usd IS NOT NULL) AS known_cost_usd,
                COUNT(*) FILTER (WHERE cost_status = 'known') AS priced_agent_runs,
                COUNT(*) FILTER (WHERE cost_status = 'partial') AS partial_cost_agent_runs,
                COUNT(*) FILTER (WHERE cost_status NOT IN ('known', 'partial')) AS unpriced_agent_runs,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY total_cost_usd) FILTER (
                    WHERE total_cost_usd IS NOT NULL
                ) AS median_agent_run_cost_usd,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY total_cost_usd) FILTER (
                    WHERE total_cost_usd IS NOT NULL
                ) AS p95_agent_run_cost_usd,
                COALESCE(SUM(total_cost_usd) FILTER (
                    WHERE status IN ('failed', 'cancelled') AND total_cost_usd IS NOT NULL
                ), 0) AS failed_spend_usd,
                COUNT(*) FILTER (
                    WHERE provider_model_id IS NULL AND model IS NULL
                ) AS missing_model_attribution,
                COUNT(*) FILTER (WHERE release_id_text IS NULL) AS missing_release_attribution,
                MAX(COALESCE(ended_at, started_at)) AS agent_data_through,
                (SELECT COUNT(*) FROM previous_runs) AS previous_agent_runs,
                (
                    SELECT SUM(total_cost_usd)
                    FROM previous_runs
                    WHERE total_cost_usd IS NOT NULL
                ) AS previous_cost_usd
            FROM current_runs
            """
        )
        row = (await self._uow.session.execute(statement, params)).mappings().one()
        runs = int(row["agent_runs"] or 0)
        previous_runs = int(row["previous_agent_runs"] or 0)
        successful = int(row["successful_agent_runs"] or 0)
        known_cost = row["known_cost_usd"]
        previous_cost = float(row["previous_cost_usd"] or 0)
        priced = int(row["priced_agent_runs"] or 0)

        return {
            "project_exists": bool(row["project_exists"]),
            "agent_runs": runs,
            "direct_agent_runs": int(row["direct_agent_runs"] or 0),
            "network_agent_runs": int(row["network_agent_runs"] or 0),
            "successful_agent_runs": successful,
            "failed_agent_runs": int(row["failed_agent_runs"] or 0),
            "cancelled_agent_runs": int(row["cancelled_agent_runs"] or 0),
            "priced_agent_runs": priced,
            "partial_cost_agent_runs": int(row["partial_cost_agent_runs"] or 0),
            "unpriced_agent_runs": int(row["unpriced_agent_runs"] or 0),
            "agent_run_change_percent": self._change(runs, previous_runs),
            "agent_run_success_rate": round((successful / runs) * 100, 2) if runs else None,
            "known_cost_usd": self._known_cost(known_cost, runs, priced),
            "cost_change_percent": self._change(float(known_cost or 0), previous_cost),
            "median_agent_run_cost_usd": self._rounded(row["median_agent_run_cost_usd"], 8),
            "p95_agent_run_cost_usd": self._rounded(row["p95_agent_run_cost_usd"], 8),
            "failed_spend_usd": round(float(row["failed_spend_usd"] or 0), 8),
            "llm_calls": int(row["llm_calls"] or 0),
            "input_tokens": int(row["input_tokens"] or 0),
            "output_tokens": int(row["output_tokens"] or 0),
            "embedding_tokens": int(row["embedding_tokens"] or 0),
            "tool_calls": int(row["tool_calls"] or 0),
            "missing_model_attribution": int(row["missing_model_attribution"] or 0),
            "missing_release_attribution": int(row["missing_release_attribution"] or 0),
            "agent_data_through": row["agent_data_through"],
        }

    async def _network_summary(self, params: dict[str, Any]) -> dict[str, Any]:
        scope = self._agent_scope_sql("agent_run")
        statement = text(
            f"""
            WITH {self._agent_run_context_cte()},
            scoped_agent_runs AS (
                SELECT *
                FROM agent_run_context AS agent_run
                WHERE {scope}
                  AND agent_run.network_execution_id IS NOT NULL
            ),
            execution_costs AS (
                SELECT
                    network_execution_id,
                    COUNT(*) AS total_agent_runs,
                    COUNT(*) FILTER (WHERE cost_status = 'known') AS priced_agent_runs,
                    COUNT(*) FILTER (WHERE cost_status = 'partial') AS partial_agent_runs,
                    COUNT(*) FILTER (WHERE cost_status NOT IN ('known', 'partial')) AS unpriced_agent_runs,
                    SUM(total_cost_usd) FILTER (WHERE total_cost_usd IS NOT NULL) AS known_cost_usd
                FROM scoped_agent_runs
                GROUP BY network_execution_id
            ),
            current_runs AS (
                SELECT
                    execution.id,
                    execution.status,
                    execution.created_at,
                    execution.started_at,
                    execution.completed_at,
                    COALESCE(costs.total_agent_runs, 0) AS total_agent_runs,
                    COALESCE(costs.priced_agent_runs, 0) AS priced_agent_runs,
                    COALESCE(costs.partial_agent_runs, 0) AS partial_agent_runs,
                    COALESCE(costs.unpriced_agent_runs, 0) AS unpriced_agent_runs,
                    costs.known_cost_usd
                FROM network.network_executions AS execution
                JOIN network.network_sessions AS network_session
                  ON network_session.id = execution.network_session_id
                LEFT JOIN execution_costs AS costs
                  ON costs.network_execution_id = execution.id
                WHERE execution.project_id = :project_id
                  AND execution.created_at >= :start
                  AND execution.created_at < :end
                  AND execution.status IN ('completed', 'failed', 'timed_out', 'uncertain', 'cancelled')
                  AND :operation <> 'agent'
                  AND (:environment = 'all' OR network_session.environment = :environment)
                  AND (CAST(:network_id AS uuid) IS NULL OR execution.network_id = CAST(:network_id AS uuid))
                  AND (
                    (CAST(:agent_id AS uuid) IS NULL AND CAST(:provider_model_id AS uuid) IS NULL AND CAST(:release_id AS uuid) IS NULL)
                    OR costs.total_agent_runs > 0
                  )
            ),
            previous_runs AS (
                SELECT execution.id
                FROM network.network_executions AS execution
                JOIN network.network_sessions AS network_session
                  ON network_session.id = execution.network_session_id
                WHERE execution.project_id = :project_id
                  AND execution.created_at >= :previous_start
                  AND execution.created_at < :start
                  AND execution.status IN ('completed', 'failed', 'timed_out', 'uncertain', 'cancelled')
                  AND :operation <> 'agent'
                  AND (:environment = 'all' OR network_session.environment = :environment)
                  AND (CAST(:network_id AS uuid) IS NULL OR execution.network_id = CAST(:network_id AS uuid))
            )
            SELECT
                COUNT(*) AS network_runs,
                COUNT(*) FILTER (WHERE status = 'completed') AS successful_network_runs,
                COUNT(*) FILTER (WHERE status IN ('failed', 'timed_out', 'uncertain')) AS failed_network_runs,
                COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_network_runs,
                COUNT(*) FILTER (
                    WHERE total_agent_runs > 0
                      AND partial_agent_runs = 0
                      AND unpriced_agent_runs = 0
                ) AS priced_network_runs,
                COUNT(*) FILTER (
                    WHERE known_cost_usd IS NOT NULL
                      AND (partial_agent_runs > 0 OR unpriced_agent_runs > 0)
                ) AS partial_cost_network_runs,
                COUNT(*) FILTER (WHERE known_cost_usd IS NULL) AS unpriced_network_runs,
                SUM(known_cost_usd) FILTER (WHERE known_cost_usd IS NOT NULL) AS network_run_cost_usd,
                SUM(known_cost_usd) FILTER (
                    WHERE total_agent_runs > 0
                      AND partial_agent_runs = 0
                      AND unpriced_agent_runs = 0
                ) AS priced_network_cost_usd,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY known_cost_usd) FILTER (
                    WHERE known_cost_usd IS NOT NULL
                ) AS median_network_run_cost_usd,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY known_cost_usd) FILTER (
                    WHERE known_cost_usd IS NOT NULL
                ) AS p95_network_run_cost_usd,
                AVG(total_agent_runs) AS avg_agent_runs_per_network_run,
                MAX(COALESCE(completed_at, started_at, created_at)) AS network_data_through,
                (SELECT COUNT(*) FROM previous_runs) AS previous_network_runs
            FROM current_runs
            """
        )
        row = (await self._uow.session.execute(statement, params)).mappings().one()
        runs = int(row["network_runs"] or 0)
        successful = int(row["successful_network_runs"] or 0)
        priced = int(row["priced_network_runs"] or 0)
        known_cost = row["network_run_cost_usd"]
        return {
            "network_runs": runs,
            "successful_network_runs": successful,
            "failed_network_runs": int(row["failed_network_runs"] or 0),
            "cancelled_network_runs": int(row["cancelled_network_runs"] or 0),
            "priced_network_runs": priced,
            "partial_cost_network_runs": int(row["partial_cost_network_runs"] or 0),
            "unpriced_network_runs": int(row["unpriced_network_runs"] or 0),
            "network_run_change_percent": self._change(
                runs,
                int(row["previous_network_runs"] or 0),
            ),
            "network_run_success_rate": round((successful / runs) * 100, 2) if runs else None,
            "network_run_cost_usd": self._known_cost(known_cost, runs, priced),
            "cost_per_priced_network_run": (
                round(float(row["priced_network_cost_usd"] or 0) / priced, 8)
                if priced
                else None
            ),
            "median_network_run_cost_usd": self._rounded(row["median_network_run_cost_usd"], 8),
            "p95_network_run_cost_usd": self._rounded(row["p95_network_run_cost_usd"], 8),
            "avg_agent_runs_per_network_run": self._rounded(
                row["avg_agent_runs_per_network_run"],
                2,
            ),
            "network_data_through": row["network_data_through"],
        }

    async def _timeseries(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        scope = self._agent_scope_sql("run")
        statement = text(
            f"""
            WITH {self._agent_run_context_cte()},
            filtered_agent_runs AS (
                SELECT *
                FROM agent_run_context AS run
                WHERE run.started_at >= :start
                  AND run.started_at < :end
                  AND {scope}
            ),
            agent_buckets AS (
                SELECT
                    date_trunc(:bucket, started_at, 'UTC') AS bucket_start,
                    COUNT(*) AS agent_runs,
                    COUNT(*) FILTER (WHERE network_execution_id IS NULL) AS direct_agent_runs,
                    COUNT(*) FILTER (WHERE network_execution_id IS NOT NULL) AS network_agent_runs,
                    COUNT(*) FILTER (WHERE status = 'completed') AS successful_agent_runs,
                    COUNT(*) FILTER (WHERE status IN ('failed', 'cancelled')) AS failed_agent_runs,
                    COALESCE(SUM(llm_calls), 0) AS llm_calls,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    SUM(total_cost_usd) FILTER (WHERE total_cost_usd IS NOT NULL) AS known_cost_usd,
                    COUNT(*) FILTER (WHERE cost_status = 'known') AS priced_agent_runs,
                    COUNT(*) FILTER (WHERE cost_status = 'partial') AS partial_cost_agent_runs,
                    COUNT(*) FILTER (WHERE cost_status NOT IN ('known', 'partial')) AS unpriced_agent_runs
                FROM filtered_agent_runs
                GROUP BY 1
            ),
            network_costs AS (
                SELECT
                    network_execution_id,
                    COUNT(*) AS agent_runs,
                    SUM(total_cost_usd) FILTER (WHERE total_cost_usd IS NOT NULL) AS known_cost_usd
                FROM filtered_agent_runs
                WHERE network_execution_id IS NOT NULL
                GROUP BY network_execution_id
            ),
            network_buckets AS (
                SELECT
                    date_trunc(:bucket, execution.created_at, 'UTC') AS bucket_start,
                    COUNT(*) AS network_runs,
                    COUNT(*) FILTER (WHERE execution.status = 'completed') AS successful_network_runs,
                    COUNT(*) FILTER (
                        WHERE execution.status IN ('failed', 'timed_out', 'uncertain', 'cancelled')
                    ) AS failed_network_runs,
                    SUM(network_costs.known_cost_usd) FILTER (
                        WHERE network_costs.known_cost_usd IS NOT NULL
                    ) AS network_run_cost_usd,
                    COUNT(network_costs.known_cost_usd) AS priced_network_runs
                FROM network.network_executions AS execution
                JOIN network.network_sessions AS network_session
                  ON network_session.id = execution.network_session_id
                LEFT JOIN network_costs
                  ON network_costs.network_execution_id = execution.id
                WHERE execution.project_id = :project_id
                  AND execution.created_at >= :start
                  AND execution.created_at < :end
                  AND execution.status IN ('completed', 'failed', 'timed_out', 'uncertain', 'cancelled')
                  AND :operation <> 'agent'
                  AND (:environment = 'all' OR network_session.environment = :environment)
                  AND (CAST(:network_id AS uuid) IS NULL OR execution.network_id = CAST(:network_id AS uuid))
                  AND (
                    (CAST(:agent_id AS uuid) IS NULL AND CAST(:provider_model_id AS uuid) IS NULL AND CAST(:release_id AS uuid) IS NULL)
                    OR network_costs.agent_runs > 0
                  )
                GROUP BY 1
            ),
            buckets AS (
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
                buckets.bucket_start,
                COALESCE(agent_buckets.agent_runs, 0) AS agent_runs,
                COALESCE(agent_buckets.direct_agent_runs, 0) AS direct_agent_runs,
                COALESCE(agent_buckets.network_agent_runs, 0) AS network_agent_runs,
                COALESCE(agent_buckets.successful_agent_runs, 0) AS successful_agent_runs,
                COALESCE(agent_buckets.failed_agent_runs, 0) AS failed_agent_runs,
                COALESCE(network_buckets.network_runs, 0) AS network_runs,
                COALESCE(network_buckets.successful_network_runs, 0) AS successful_network_runs,
                COALESCE(network_buckets.failed_network_runs, 0) AS failed_network_runs,
                agent_buckets.known_cost_usd,
                network_buckets.network_run_cost_usd,
                COALESCE(agent_buckets.llm_calls, 0) AS llm_calls,
                COALESCE(agent_buckets.input_tokens, 0) AS input_tokens,
                COALESCE(agent_buckets.output_tokens, 0) AS output_tokens,
                COALESCE(agent_buckets.priced_agent_runs, 0) AS priced_agent_runs,
                COALESCE(agent_buckets.partial_cost_agent_runs, 0) AS partial_cost_agent_runs,
                COALESCE(agent_buckets.unpriced_agent_runs, 0) AS unpriced_agent_runs,
                COALESCE(network_buckets.priced_network_runs, 0) AS priced_network_runs
            FROM buckets
            LEFT JOIN agent_buckets USING (bucket_start)
            LEFT JOIN network_buckets USING (bucket_start)
            ORDER BY buckets.bucket_start
            """
        )
        rows = (await self._uow.session.execute(statement, params)).mappings().all()
        points: list[dict[str, Any]] = []
        for row in rows:
            agent_runs = int(row["agent_runs"] or 0)
            network_runs = int(row["network_runs"] or 0)
            agent_cost = self._known_cost(
                row["known_cost_usd"],
                agent_runs,
                int(row["priced_agent_runs"] or 0),
            )
            network_cost = self._known_cost(
                row["network_run_cost_usd"],
                network_runs,
                int(row["priced_network_runs"] or 0),
            )
            priced_agent_runs = int(row["priced_agent_runs"] or 0)
            priced_network_runs = int(row["priced_network_runs"] or 0)
            point = {
                "bucket_start": row["bucket_start"],
                "agent_runs": agent_runs,
                "direct_agent_runs": int(row["direct_agent_runs"] or 0),
                "network_agent_runs": int(row["network_agent_runs"] or 0),
                "successful_agent_runs": int(row["successful_agent_runs"] or 0),
                "failed_agent_runs": int(row["failed_agent_runs"] or 0),
                "network_runs": network_runs,
                "successful_network_runs": int(row["successful_network_runs"] or 0),
                "failed_network_runs": int(row["failed_network_runs"] or 0),
                "known_cost_usd": agent_cost,
                "network_run_cost_usd": network_cost,
                "agent_cost_per_run": (
                    round(float(agent_cost) / priced_agent_runs, 8)
                    if agent_cost is not None and priced_agent_runs
                    else None
                ),
                "network_cost_per_run": (
                    round(float(network_cost) / priced_network_runs, 8)
                    if network_cost is not None and priced_network_runs
                    else None
                ),
                "llm_calls": int(row["llm_calls"] or 0),
                "input_tokens": int(row["input_tokens"] or 0),
                "output_tokens": int(row["output_tokens"] or 0),
                "priced_agent_runs": priced_agent_runs,
                "partial_cost_agent_runs": int(row["partial_cost_agent_runs"] or 0),
                "unpriced_agent_runs": int(row["unpriced_agent_runs"] or 0),
                "runtime_requests": agent_runs,
                "successful_requests": int(row["successful_agent_runs"] or 0),
                "failed_requests": int(row["failed_agent_runs"] or 0),
                "priced_requests": priced_agent_runs,
                "partial_cost_requests": int(row["partial_cost_agent_runs"] or 0),
                "unpriced_requests": int(row["unpriced_agent_runs"] or 0),
            }
            points.append(point)
        return points

    async def _breakdown(
        self,
        params: dict[str, Any],
        group_by: str,
    ) -> list[dict[str, Any]]:
        key_sql, label_sql = _GROUP_SQL[group_by]
        scope = self._agent_scope_sql("filtered")
        statement = text(
            f"""
            WITH {self._agent_run_context_cte()},
            filtered AS (
                SELECT *
                FROM agent_run_context AS filtered
                WHERE filtered.started_at >= :start
                  AND filtered.started_at < :end
                  AND {scope}
            )
            SELECT
                {key_sql} AS key,
                {label_sql} AS label,
                SUM(filtered.total_cost_usd) FILTER (
                    WHERE filtered.total_cost_usd IS NOT NULL
                ) AS known_cost_usd,
                COUNT(*) AS agent_runs,
                COUNT(DISTINCT filtered.network_execution_id) FILTER (
                    WHERE filtered.network_execution_id IS NOT NULL
                ) AS network_runs,
                COUNT(*) FILTER (WHERE filtered.status = 'completed') AS successful_agent_runs,
                COALESCE(SUM(filtered.llm_calls), 0) AS llm_calls,
                COALESCE(SUM(filtered.input_tokens), 0) AS input_tokens,
                COALESCE(SUM(filtered.output_tokens), 0) AS output_tokens,
                COUNT(*) FILTER (WHERE filtered.cost_status = 'known') AS priced_agent_runs
            FROM filtered
            GROUP BY 1, 2
            ORDER BY known_cost_usd DESC NULLS LAST, agent_runs DESC
            LIMIT :top_limit
            """
        )
        rows = (await self._uow.session.execute(statement, params)).mappings().all()
        return [
            {
                "key": str(row["key"]),
                "label": str(row["label"]),
                "known_cost_usd": (
                    round(float(row["known_cost_usd"]), 8)
                    if row["known_cost_usd"] is not None
                    else None
                ),
                "agent_runs": int(row["agent_runs"] or 0),
                "network_runs": int(row["network_runs"] or 0),
                "successful_agent_runs": int(row["successful_agent_runs"] or 0),
                "llm_calls": int(row["llm_calls"] or 0),
                "input_tokens": int(row["input_tokens"] or 0),
                "output_tokens": int(row["output_tokens"] or 0),
                "priced_agent_runs": int(row["priced_agent_runs"] or 0),
            }
            for row in rows
        ]

    async def _top_executions(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        direct_runs = await self._top_direct_agent_runs(params)
        network_runs = await self._top_network_runs(params)
        executions = [*direct_runs, *network_runs]
        executions.sort(
            key=lambda item: (
                item["known_cost_usd"] is not None,
                float(item["known_cost_usd"] or 0),
                item["started_at"] or datetime.min.replace(tzinfo=UTC),
            ),
            reverse=True,
        )
        return executions[: int(params["top_limit"])]

    async def _top_direct_agent_runs(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        scope = self._agent_scope_sql("run")
        statement = text(
            f"""
            WITH {self._agent_run_context_cte()}
            SELECT *
            FROM agent_run_context AS run
            WHERE run.started_at >= :start
              AND run.started_at < :end
              AND run.network_execution_id IS NULL
              AND :operation <> 'network'
              AND {scope}
            ORDER BY run.total_cost_usd DESC NULLS LAST, run.started_at DESC
            LIMIT :top_limit
            """
        )
        rows = (await self._uow.session.execute(statement, params)).mappings().all()
        results: list[dict[str, Any]] = []
        for row in rows:
            release_id: UUID | None = None
            try:
                if row["release_id_text"]:
                    release_id = UUID(str(row["release_id_text"]))
            except (TypeError, ValueError):
                release_id = None
            results.append(
                {
                    "run_id": row["trace_id"],
                    "run_type": "agent",
                    "trace_id": row["trace_id"],
                    "network_id": None,
                    "network_name": None,
                    "network_execution_id": None,
                    "network_version_id": None,
                    "agent_id": row["agent_id"],
                    "agent_name": row["agent_name"],
                    "environment": row["run_environment"],
                    "release_id": release_id,
                    "release_version": row["release_version"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "status": row["status"],
                    "llm_calls": int(row["llm_calls"] or 0),
                    "input_tokens": int(row["input_tokens"] or 0),
                    "output_tokens": int(row["output_tokens"] or 0),
                    "tool_calls": int(row["tool_calls"] or 0),
                    "agent_runs_count": 1,
                    "duration_ms": self._rounded(row["total_latency_ms"]),
                    "known_cost_usd": (
                        round(float(row["total_cost_usd"]), 8)
                        if row["total_cost_usd"] is not None
                        else None
                    ),
                    "cost_status": row["cost_status"],
                    "started_at": row["started_at"],
                }
            )
        return results

    async def _top_network_runs(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        scope = self._agent_scope_sql("agent_run")
        statement = text(
            f"""
            WITH {self._agent_run_context_cte()},
            scoped_agent_runs AS (
                SELECT *
                FROM agent_run_context AS agent_run
                WHERE {scope}
                  AND agent_run.network_execution_id IS NOT NULL
            ),
            costs AS (
                SELECT
                    network_execution_id,
                    COUNT(*) AS agent_runs_count,
                    COALESCE(SUM(llm_calls), 0) AS llm_calls,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(tool_calls), 0) AS tool_calls,
                    SUM(total_cost_usd) FILTER (WHERE total_cost_usd IS NOT NULL) AS known_cost_usd,
                    COUNT(*) FILTER (WHERE cost_status = 'known') AS priced_runs,
                    COUNT(*) FILTER (WHERE cost_status = 'partial') AS partial_runs,
                    COUNT(*) FILTER (WHERE cost_status NOT IN ('known', 'partial')) AS unpriced_runs
                FROM scoped_agent_runs
                GROUP BY network_execution_id
            )
            SELECT
                execution.id AS run_id,
                execution.network_id,
                network.name AS network_name,
                execution.network_version_id,
                execution.root_trace_id,
                network_session.environment,
                execution.status,
                execution.created_at,
                execution.started_at,
                execution.completed_at,
                COALESCE(costs.agent_runs_count, 0) AS agent_runs_count,
                COALESCE(costs.llm_calls, 0) AS llm_calls,
                COALESCE(costs.input_tokens, 0) AS input_tokens,
                COALESCE(costs.output_tokens, 0) AS output_tokens,
                COALESCE(costs.tool_calls, 0) AS tool_calls,
                costs.known_cost_usd,
                COALESCE(costs.priced_runs, 0) AS priced_runs,
                COALESCE(costs.partial_runs, 0) AS partial_runs,
                COALESCE(costs.unpriced_runs, 0) AS unpriced_runs
            FROM network.network_executions AS execution
            JOIN network.networks AS network ON network.id = execution.network_id
            JOIN network.network_sessions AS network_session
              ON network_session.id = execution.network_session_id
            LEFT JOIN costs ON costs.network_execution_id = execution.id
            WHERE execution.project_id = :project_id
              AND execution.created_at >= :start
              AND execution.created_at < :end
              AND execution.status IN ('completed', 'failed', 'timed_out', 'uncertain', 'cancelled')
              AND :operation <> 'agent'
              AND (:environment = 'all' OR network_session.environment = :environment)
              AND (CAST(:network_id AS uuid) IS NULL OR execution.network_id = CAST(:network_id AS uuid))
              AND (
                (CAST(:agent_id AS uuid) IS NULL AND CAST(:provider_model_id AS uuid) IS NULL AND CAST(:release_id AS uuid) IS NULL)
                OR costs.agent_runs_count > 0
              )
            ORDER BY costs.known_cost_usd DESC NULLS LAST, execution.created_at DESC
            LIMIT :top_limit
            """
        )
        rows = (await self._uow.session.execute(statement, params)).mappings().all()
        results: list[dict[str, Any]] = []
        for row in rows:
            known = row["known_cost_usd"]
            agent_runs = int(row["agent_runs_count"] or 0)
            priced = int(row["priced_runs"] or 0)
            partial = int(row["partial_runs"] or 0)
            unpriced = int(row["unpriced_runs"] or 0)
            if known is None:
                cost_status = "unknown"
            elif agent_runs > 0 and priced == agent_runs and partial == 0 and unpriced == 0:
                cost_status = "known"
            else:
                cost_status = "partial"
            duration_ms = None
            if row["started_at"] is not None and row["completed_at"] is not None:
                duration_ms = round(
                    (row["completed_at"] - row["started_at"]).total_seconds() * 1000,
                    2,
                )
            results.append(
                {
                    "run_id": row["run_id"],
                    "run_type": "network",
                    "trace_id": row["root_trace_id"],
                    "network_id": row["network_id"],
                    "network_name": row["network_name"],
                    "network_execution_id": row["run_id"],
                    "network_version_id": row["network_version_id"],
                    "agent_id": None,
                    "agent_name": None,
                    "environment": row["environment"],
                    "release_id": None,
                    "release_version": None,
                    "provider": None,
                    "model": None,
                    "status": row["status"],
                    "llm_calls": int(row["llm_calls"] or 0),
                    "input_tokens": int(row["input_tokens"] or 0),
                    "output_tokens": int(row["output_tokens"] or 0),
                    "tool_calls": int(row["tool_calls"] or 0),
                    "agent_runs_count": agent_runs,
                    "duration_ms": duration_ms,
                    "known_cost_usd": round(float(known), 8) if known is not None else None,
                    "cost_status": cost_status,
                    "started_at": row["started_at"] or row["created_at"],
                }
            )
        return results

    @staticmethod
    def _change(current: float, previous: float) -> float | None:
        if previous:
            return round(((current - previous) / previous) * 100, 2)
        if current == 0:
            return 0.0
        return None

    @staticmethod
    def _known_cost(value: Any, total: int, priced: int) -> float | None:
        if total == 0:
            return 0.0
        if priced == 0 or value is None:
            return None
        return round(float(value), 8)

    @staticmethod
    def _rounded(value: Any, digits: int = 2) -> float | None:
        return round(float(value), digits) if value is not None else None

    @staticmethod
    def _latest_timestamp(*values: datetime | None) -> datetime | None:
        present = [value for value in values if value is not None]
        return max(present) if present else None
