from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text

from modules.metering.application.dtos.project_usage import ProjectUsageQuery
from modules.metering.infra.database.unit_of_work import MeteringUnitOfWork
from shared.infra.errors import NotFoundError

_ENVIRONMENT_SQL = """
COALESCE(
    NULLIF(trace.data ->> 'execution_context', ''),
    NULLIF(trace.data -> 'diagnostics' ->> 'execution_context', ''),
    NULLIF(trace.data ->> 'environment', ''),
    'draft'
)
"""

_RELEASE_ID_SQL = """
COALESCE(
    NULLIF(trace.data ->> 'agent_release_id', ''),
    NULLIF(trace.data -> 'diagnostics' ->> 'agent_release_id', '')
)
"""

_RELEASE_VERSION_SQL = """
COALESCE(
    NULLIF(trace.data ->> 'agent_release_version', ''),
    NULLIF(trace.data -> 'diagnostics' ->> 'agent_release_version', '')
)
"""

_LLM_CALLS_SQL = """
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
)
"""

_TOOL_CALLS_SQL = """
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
)
"""

_BASE_FILTER_SQL = f"""
trace.project_id = :project_id
AND trace.started_at >= :start
AND trace.started_at < :end
AND trace.status IN ('completed', 'failed', 'cancelled')
AND (:environment = 'all' OR {_ENVIRONMENT_SQL} = :environment)
AND (CAST(:network_id AS uuid) IS NULL OR trace.network_id = CAST(:network_id AS uuid))
AND (CAST(:agent_id AS uuid) IS NULL OR trace.agent_id = CAST(:agent_id AS uuid))
AND (
    CAST(:provider_model_id AS uuid) IS NULL
    OR trace.provider_model_id = CAST(:provider_model_id AS uuid)
    OR trace.data ->> 'provider_model_id' = CAST(:provider_model_id AS text)
    OR trace.data -> 'diagnostics' ->> 'provider_model_id' = CAST(:provider_model_id AS text)
)
AND (
    CAST(:release_id AS uuid) IS NULL
    OR {_RELEASE_ID_SQL} = CAST(:release_id AS text)
)
"""

_TRACE_FIELDS_SQL = f"""
trace.id AS trace_id,
trace.network_id,
network.name AS network_name,
trace.network_execution_id,
trace.network_version_id,
trace.agent_id,
agent.name AS agent_name,
trace.status,
trace.started_at,
trace.ended_at,
trace.total_cost_usd,
trace.provider,
trace.model,
trace.provider_model_id,
{_ENVIRONMENT_SQL} AS environment,
{_RELEASE_ID_SQL} AS release_id_text,
{_RELEASE_VERSION_SQL} AS release_version,
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
{_LLM_CALLS_SQL} AS llm_calls,
{_TOOL_CALLS_SQL} AS tool_calls,
COALESCE(
    NULLIF(trace.data ->> 'cost_status', ''),
    NULLIF(trace.data -> 'diagnostics' ->> 'cost_status', ''),
    CASE WHEN trace.total_cost_usd IS NULL THEN 'unknown' ELSE 'known' END
) AS cost_status
"""

_GROUP_SQL: dict[str, tuple[str, str]] = {
    "agent": (
        "COALESCE(filtered.agent_id::text, 'unattributed')",
        "COALESCE(filtered.agent_name, 'Unattributed agent')",
    ),
    "model": (
        "COALESCE(filtered.provider_model_id::text, filtered.model, 'unattributed')",
        "COALESCE(NULLIF(CONCAT_WS(' / ', filtered.provider, filtered.model), ''), 'Unattributed model')",
    ),
    "provider": (
        "COALESCE(filtered.provider, 'unattributed')",
        "COALESCE(filtered.provider, 'Unattributed provider')",
    ),
    "environment": (
        "filtered.environment",
        "INITCAP(filtered.environment)",
    ),
    "release": (
        "COALESCE(filtered.release_id_text, 'unattributed')",
        "COALESCE(filtered.release_version, filtered.release_id_text, 'Unattributed release')",
    ),
}


class SQLAlchemyProjectUsageReader:
    def __init__(self, uow: MeteringUnitOfWork) -> None:
        self._uow = uow

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
            "network_id": query.network_id,
            "agent_id": query.agent_id,
            "provider_model_id": query.provider_model_id,
            "release_id": query.release_id,
            "bucket": query.bucket,
            "step": timedelta(hours=1) if query.bucket == "hour" else timedelta(days=1),
            "top_limit": query.top_limit,
        }
        raw_summary = await self._summary(params)
        if not raw_summary.pop("project_exists"):
            raise NotFoundError("Project not found")

        timeseries = await self._timeseries(params)
        breakdown = await self._breakdown(params, query.group_by)
        top_executions = await self._top_executions(params)

        runtime_requests = int(raw_summary["runtime_requests"])
        priced_requests = int(raw_summary["priced_requests"])
        known_cost = raw_summary["known_cost_usd"]
        input_tokens = int(raw_summary["input_tokens"])
        output_tokens = int(raw_summary["output_tokens"])
        previous_requests = int(raw_summary.pop("previous_requests"))
        previous_cost = float(raw_summary.pop("previous_cost_usd"))
        data_through = raw_summary.pop("data_through")
        embedding_tokens = int(raw_summary.pop("embedding_tokens"))
        tool_calls = int(raw_summary.pop("tool_calls"))
        missing_model = int(raw_summary.pop("missing_model_attribution"))
        missing_release = int(raw_summary.pop("missing_release_attribution"))

        raw_summary["cost_coverage_percent"] = (
            round((priced_requests / runtime_requests) * 100, 2)
            if runtime_requests
            else None
        )
        raw_summary["cost_per_priced_request"] = (
            round(float(known_cost) / priced_requests, 8)
            if known_cost is not None and priced_requests
            else None
        )
        raw_summary["tokens_per_request"] = (
            round((input_tokens + output_tokens) / runtime_requests, 2)
            if runtime_requests
            else None
        )
        raw_summary["request_change_percent"] = self._change(
            runtime_requests,
            previous_requests,
        )
        raw_summary["cost_change_percent"] = self._change(
            float(known_cost or 0),
            previous_cost,
        )

        total_cost = float(known_cost or 0)
        for row in breakdown:
            row_cost = float(row.get("known_cost_usd") or 0)
            row["share_percent"] = (
                round((row_cost / total_cost) * 100, 2) if total_cost else 0.0
            )
            row_priced = int(row.pop("priced_requests", 0))
            row_requests = int(row["runtime_requests"])
            row["cost_per_priced_request"] = (
                round(row_cost / row_priced, 8) if row_priced else None
            )
            row["cost_coverage_percent"] = (
                round((row_priced / row_requests) * 100, 2)
                if row_requests
                else None
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
            "group_by": query.group_by,
            "summary": raw_summary,
            "timeseries": timeseries,
            "composition": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "embedding_tokens": embedding_tokens,
                "tool_calls": tool_calls,
                "vector_queries": 0,
            },
            "breakdown": breakdown,
            "top_executions": top_executions,
            "data_quality": {
                "fully_priced_requests": priced_requests,
                "partial_requests": int(raw_summary["partial_cost_requests"]),
                "unpriced_requests": int(raw_summary["unpriced_requests"]),
                "missing_model_attribution": missing_model,
                "missing_release_attribution": missing_release,
                "aggregation_lag_seconds": freshness_seconds,
            },
        }

    async def _summary(self, params: dict[str, Any]) -> dict[str, Any]:
        statement = text(
            f"""
            WITH current_traces AS (
                SELECT {_TRACE_FIELDS_SQL}
                FROM observability.traces AS trace
                LEFT JOIN agent.agents AS agent ON agent.id = trace.agent_id
                LEFT JOIN network.networks AS network ON network.id = trace.network_id
                WHERE {_BASE_FILTER_SQL}
            ),
            previous_traces AS (
                SELECT trace.total_cost_usd
                FROM observability.traces AS trace
                WHERE trace.project_id = :project_id
                  AND trace.started_at >= :previous_start
                  AND trace.started_at < :start
                  AND trace.status IN ('completed', 'failed', 'cancelled')
                  AND (:environment = 'all' OR {_ENVIRONMENT_SQL} = :environment)
                  AND (CAST(:network_id AS uuid) IS NULL OR trace.network_id = CAST(:network_id AS uuid))
                  AND (CAST(:agent_id AS uuid) IS NULL OR trace.agent_id = CAST(:agent_id AS uuid))
                  AND (
                    CAST(:provider_model_id AS uuid) IS NULL
                    OR trace.provider_model_id = CAST(:provider_model_id AS uuid)
                    OR trace.data ->> 'provider_model_id' = CAST(:provider_model_id AS text)
                    OR trace.data -> 'diagnostics' ->> 'provider_model_id' = CAST(:provider_model_id AS text)
                  )
                  AND (
                    CAST(:release_id AS uuid) IS NULL
                    OR {_RELEASE_ID_SQL} = CAST(:release_id AS text)
                  )
            )
            SELECT
                EXISTS(SELECT 1 FROM core.projects WHERE id = :project_id) AS project_exists,
                COUNT(*) AS runtime_requests,
                COUNT(*) FILTER (WHERE status = 'completed') AS successful_requests,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed_requests,
                COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_requests,
                COALESCE(SUM(llm_calls), 0) AS llm_calls,
                COALESCE(SUM(input_tokens), 0) AS input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(embedding_tokens), 0) AS embedding_tokens,
                COALESCE(SUM(tool_calls), 0) AS tool_calls,
                SUM(total_cost_usd) FILTER (WHERE total_cost_usd IS NOT NULL) AS known_cost_usd,
                COUNT(*) FILTER (WHERE cost_status = 'known') AS priced_requests,
                COUNT(*) FILTER (WHERE cost_status = 'partial') AS partial_cost_requests,
                COUNT(*) FILTER (WHERE cost_status NOT IN ('known', 'partial')) AS unpriced_requests,
                COALESCE(SUM(total_cost_usd) FILTER (
                    WHERE status IN ('failed', 'cancelled')
                      AND total_cost_usd IS NOT NULL
                ), 0) AS failed_spend_usd,
                COUNT(*) FILTER (
                    WHERE provider_model_id IS NULL AND model IS NULL
                ) AS missing_model_attribution,
                COUNT(*) FILTER (
                    WHERE release_id_text IS NULL
                ) AS missing_release_attribution,
                MAX(COALESCE(ended_at, started_at)) AS data_through,
                (SELECT COUNT(*) FROM previous_traces) AS previous_requests,
                (
                    SELECT SUM(total_cost_usd)
                    FROM previous_traces
                    WHERE total_cost_usd IS NOT NULL
                ) AS previous_cost_usd
            FROM current_traces
            """
        )
        row = (await self._uow.session.execute(statement, params)).mappings().one()
        requests = int(row["runtime_requests"] or 0)
        known_cost = row["known_cost_usd"]
        return {
            "project_exists": bool(row["project_exists"]),
            "runtime_requests": requests,
            "successful_requests": int(row["successful_requests"] or 0),
            "failed_requests": int(row["failed_requests"] or 0),
            "cancelled_requests": int(row["cancelled_requests"] or 0),
            "llm_calls": int(row["llm_calls"] or 0),
            "input_tokens": int(row["input_tokens"] or 0),
            "output_tokens": int(row["output_tokens"] or 0),
            "embedding_tokens": int(row["embedding_tokens"] or 0),
            "tool_calls": int(row["tool_calls"] or 0),
            "known_cost_usd": (
                round(float(known_cost), 8)
                if known_cost is not None
                else (0.0 if requests == 0 else None)
            ),
            "priced_requests": int(row["priced_requests"] or 0),
            "partial_cost_requests": int(row["partial_cost_requests"] or 0),
            "unpriced_requests": int(row["unpriced_requests"] or 0),
            "failed_spend_usd": round(float(row["failed_spend_usd"] or 0), 8),
            "missing_model_attribution": int(row["missing_model_attribution"] or 0),
            "missing_release_attribution": int(row["missing_release_attribution"] or 0),
            "data_through": row["data_through"],
            "previous_requests": int(row["previous_requests"] or 0),
            "previous_cost_usd": round(float(row["previous_cost_usd"] or 0), 8),
        }

    async def _timeseries(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        statement = text(
            f"""
            WITH filtered AS (
                SELECT
                    date_trunc(:bucket, trace.started_at) AS bucket_start,
                    trace.status,
                    trace.total_cost_usd,
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
                    {_LLM_CALLS_SQL} AS llm_calls,
                    COALESCE(
                        NULLIF(trace.data ->> 'cost_status', ''),
                        NULLIF(trace.data -> 'diagnostics' ->> 'cost_status', ''),
                        CASE
                            WHEN trace.total_cost_usd IS NULL THEN 'unknown'
                            ELSE 'known'
                        END
                    ) AS cost_status
                FROM observability.traces AS trace
                WHERE {_BASE_FILTER_SQL}
            ),
            buckets AS (
                SELECT generate_series(
                    date_trunc(:bucket, CAST(:start AS timestamptz)),
                    date_trunc(
                        :bucket,
                        CAST(:end AS timestamptz) - interval '1 microsecond'
                    ),
                    CAST(:step AS interval)
                ) AS bucket_start
            ),
            aggregated AS (
                SELECT
                    bucket_start,
                    COUNT(*) AS runtime_requests,
                    COUNT(*) FILTER (WHERE status = 'completed') AS successful_requests,
                    COUNT(*) FILTER (
                        WHERE status IN ('failed', 'cancelled')
                    ) AS failed_requests,
                    COALESCE(SUM(llm_calls), 0) AS llm_calls,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    SUM(total_cost_usd) FILTER (
                        WHERE total_cost_usd IS NOT NULL
                    ) AS known_cost_usd,
                    COUNT(*) FILTER (WHERE cost_status = 'known') AS priced_requests,
                    COUNT(*) FILTER (WHERE cost_status = 'partial') AS partial_cost_requests,
                    COUNT(*) FILTER (
                        WHERE cost_status NOT IN ('known', 'partial')
                    ) AS unpriced_requests
                FROM filtered
                GROUP BY bucket_start
            )
            SELECT
                buckets.bucket_start,
                COALESCE(aggregated.runtime_requests, 0) AS runtime_requests,
                COALESCE(aggregated.successful_requests, 0) AS successful_requests,
                COALESCE(aggregated.failed_requests, 0) AS failed_requests,
                COALESCE(aggregated.llm_calls, 0) AS llm_calls,
                COALESCE(aggregated.input_tokens, 0) AS input_tokens,
                COALESCE(aggregated.output_tokens, 0) AS output_tokens,
                aggregated.known_cost_usd,
                COALESCE(aggregated.priced_requests, 0) AS priced_requests,
                COALESCE(aggregated.partial_cost_requests, 0) AS partial_cost_requests,
                COALESCE(aggregated.unpriced_requests, 0) AS unpriced_requests
            FROM buckets
            LEFT JOIN aggregated USING (bucket_start)
            ORDER BY buckets.bucket_start
            """
        )
        rows = (await self._uow.session.execute(statement, params)).mappings().all()
        points: list[dict[str, Any]] = []
        for row in rows:
            requests = int(row["runtime_requests"] or 0)
            known_cost = row["known_cost_usd"]
            points.append(
                {
                    "bucket_start": row["bucket_start"],
                    "runtime_requests": requests,
                    "successful_requests": int(row["successful_requests"] or 0),
                    "failed_requests": int(row["failed_requests"] or 0),
                    "llm_calls": int(row["llm_calls"] or 0),
                    "input_tokens": int(row["input_tokens"] or 0),
                    "output_tokens": int(row["output_tokens"] or 0),
                    "known_cost_usd": (
                        round(float(known_cost), 8)
                        if known_cost is not None
                        else (0.0 if requests == 0 else None)
                    ),
                    "priced_requests": int(row["priced_requests"] or 0),
                    "partial_cost_requests": int(row["partial_cost_requests"] or 0),
                    "unpriced_requests": int(row["unpriced_requests"] or 0),
                }
            )
        return points

    async def _breakdown(
        self,
        params: dict[str, Any],
        group_by: str,
    ) -> list[dict[str, Any]]:
        key_sql, label_sql = _GROUP_SQL[group_by]
        statement = text(
            f"""
            WITH filtered AS (
                SELECT {_TRACE_FIELDS_SQL}
                FROM observability.traces AS trace
                LEFT JOIN agent.agents AS agent ON agent.id = trace.agent_id
                LEFT JOIN network.networks AS network ON network.id = trace.network_id
                WHERE {_BASE_FILTER_SQL}
            )
            SELECT
                {key_sql} AS key,
                {label_sql} AS label,
                SUM(filtered.total_cost_usd) FILTER (
                    WHERE filtered.total_cost_usd IS NOT NULL
                ) AS known_cost_usd,
                COUNT(*) AS runtime_requests,
                COUNT(*) FILTER (
                    WHERE filtered.status = 'completed'
                ) AS successful_requests,
                COALESCE(SUM(filtered.llm_calls), 0) AS llm_calls,
                COALESCE(SUM(filtered.input_tokens), 0) AS input_tokens,
                COALESCE(SUM(filtered.output_tokens), 0) AS output_tokens,
                COUNT(*) FILTER (
                    WHERE filtered.cost_status = 'known'
                ) AS priced_requests
            FROM filtered
            GROUP BY 1, 2
            ORDER BY known_cost_usd DESC NULLS LAST, runtime_requests DESC
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
                "runtime_requests": int(row["runtime_requests"] or 0),
                "successful_requests": int(row["successful_requests"] or 0),
                "llm_calls": int(row["llm_calls"] or 0),
                "input_tokens": int(row["input_tokens"] or 0),
                "output_tokens": int(row["output_tokens"] or 0),
                "priced_requests": int(row["priced_requests"] or 0),
            }
            for row in rows
        ]

    async def _top_executions(
        self,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        statement = text(
            f"""
            SELECT {_TRACE_FIELDS_SQL}
            FROM observability.traces AS trace
            LEFT JOIN agent.agents AS agent ON agent.id = trace.agent_id
            LEFT JOIN network.networks AS network ON network.id = trace.network_id
            WHERE {_BASE_FILTER_SQL}
            ORDER BY trace.total_cost_usd DESC NULLS LAST, trace.started_at DESC
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
                    "trace_id": row["trace_id"],
                    "network_id": row["network_id"],
                    "network_name": row["network_name"],
                    "network_execution_id": row["network_execution_id"],
                    "network_version_id": row["network_version_id"],
                    "agent_id": row["agent_id"],
                    "agent_name": row["agent_name"],
                    "environment": row["environment"],
                    "release_id": release_id,
                    "release_version": row["release_version"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "status": row["status"],
                    "llm_calls": int(row["llm_calls"] or 0),
                    "input_tokens": int(row["input_tokens"] or 0),
                    "output_tokens": int(row["output_tokens"] or 0),
                    "tool_calls": int(row["tool_calls"] or 0),
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

    @staticmethod
    def _change(current: float, previous: float) -> float | None:
        if previous:
            return round(((current - previous) / previous) * 100, 2)
        if current == 0:
            return 0.0
        return None
