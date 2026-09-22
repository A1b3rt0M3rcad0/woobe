from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.errors import NotFoundError


class _CoreSessionProvider(Protocol):
    @property
    def session(self) -> AsyncSession: ...


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else None


def _rounded(value: Any) -> int | float | None:
    if value is None:
        return None
    rounded = round(float(value), 3)
    return int(rounded) if rounded.is_integer() else rounded


def _agent_run(row: Any) -> dict[str, Any]:
    result = dict(row["result"] or {})
    usage = dict(row["usage"] or {})
    result_usage = result.get("usage")
    if not usage and isinstance(result_usage, dict):
        usage = dict(result_usage)
    return {
        "id": str(row["id"]),
        "trace_id": str(row["trace_id"]),
        "project_id": str(row["project_id"]),
        "agent_id": str(row["agent_id"]),
        "agent_name": str(row["agent_name"] or "Agent"),
        "session_id": str(row["session_id"]) if row["session_id"] else None,
        "network_execution_id": (
            str(row["network_execution_id"])
            if row["network_execution_id"]
            else None
        ),
        "network_invocation_id": (
            str(row["network_invocation_id"])
            if row["network_invocation_id"]
            else None
        ),
        "parent_run_id": str(row["parent_run_id"]) if row["parent_run_id"] else None,
        "environment": str(row["environment"]),
        "origin": str(row["origin"]),
        "status": str(row["status"]),
        "input_message": str(row["input_message"]),
        "usage": usage or None,
        "result": result or None,
        "failure_code": row["failure_code"],
        "failure_detail": row["failure_detail"],
        "started_at": _iso(row["started_at"]),
        "completed_at": _iso(row["completed_at"]),
        "created_at": _iso(row["created_at"]),
    }


class SQLProjectRunsReader:
    """Canonical Project Run ledger over AgentRun and NetworkExecution storage.

    Trace rows are evidence, not the authority for Run existence. This reader keeps
    the Runs page correct even when Observability projection is delayed or absent.
    """

    def __init__(self, uow: _CoreSessionProvider) -> None:
        self._uow = uow

    async def fetch(
        self,
        *,
        project_id: UUID,
        network_id: UUID | None,
        limit: int,
    ) -> dict[str, Any]:
        session = self._uow.session
        params = {
            "project_id": project_id,
            "network_id": network_id,
            "limit": limit,
        }

        exists = await session.scalar(
            text("SELECT id FROM core.projects WHERE id = :project_id"),
            {"project_id": project_id},
        )
        if exists is None:
            raise NotFoundError("Project not found")

        summary = await self._summary(session, params)
        direct_runs = await self._direct_runs(session, params)
        network_runs = await self._network_runs(session, params)
        await self._attach_child_runs(session, network_runs)

        return {
            "summary": summary,
            "direct_agent_runs": direct_runs,
            "network_runs": network_runs,
        }

    async def _summary(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        statement = text(
            """
            WITH selected_network_executions AS (
                SELECT execution.*
                FROM network.network_executions AS execution
                WHERE execution.project_id = :project_id
                  AND (
                    :network_id IS NULL
                    OR execution.network_id = :network_id
                  )
            ),
            selected_agent_runs AS (
                SELECT run.*
                FROM agent.agent_runs AS run
                WHERE run.project_id = :project_id
                  AND (
                    :network_id IS NULL
                    OR run.network_execution_id IN (
                        SELECT id FROM selected_network_executions
                    )
                  )
            ),
            direct_runs AS (
                SELECT *
                FROM selected_agent_runs
                WHERE network_execution_id IS NULL
                  AND :network_id IS NULL
            ),
            network_child_counts AS (
                SELECT
                    execution.id AS network_execution_id,
                    COUNT(run.id) AS agent_run_count,
                    execution.status
                FROM selected_network_executions AS execution
                LEFT JOIN selected_agent_runs AS run
                  ON run.network_execution_id = execution.id
                GROUP BY execution.id, execution.status
            ),
            top_level AS (
                SELECT
                    status,
                    EXTRACT(
                        EPOCH FROM (completed_at - started_at)
                    ) * 1000 AS duration_ms
                FROM direct_runs

                UNION ALL

                SELECT
                    status,
                    EXTRACT(
                        EPOCH FROM (completed_at - started_at)
                    ) * 1000 AS duration_ms
                FROM selected_network_executions
            )
            SELECT
                (SELECT COUNT(*) FROM selected_agent_runs) AS agent_runs,
                (SELECT COUNT(*) FROM direct_runs) AS direct_agent_runs,
                (
                    SELECT COUNT(*)
                    FROM selected_agent_runs
                    WHERE network_execution_id IS NOT NULL
                ) AS network_agent_runs,
                (
                    SELECT COUNT(*)
                    FROM selected_network_executions
                ) AS network_runs,
                (
                    SELECT COUNT(*)
                    FROM top_level
                    WHERE status IN (
                        'running', 'queued', 'processing', 'cancel_requested'
                    )
                ) AS active_top_level_runs,
                (
                    SELECT COUNT(*)
                    FROM top_level
                    WHERE status IN ('failed', 'timed_out', 'uncertain')
                ) AS failed_top_level_runs,
                (SELECT COUNT(*) FROM top_level) AS top_level_runs,
                (
                    SELECT percentile_cont(0.95) WITHIN GROUP (
                        ORDER BY duration_ms
                    )
                    FROM top_level
                    WHERE duration_ms IS NOT NULL
                      AND duration_ms >= 0
                ) AS p95_top_level_latency_ms,
                (
                    SELECT AVG(agent_run_count)
                    FROM network_child_counts
                    WHERE status NOT IN ('queued', 'cancel_requested')
                ) AS avg_agent_runs_per_network_run
            """
        )
        row = (await session.execute(statement, params)).mappings().one()
        top_level = int(row["top_level_runs"] or 0)
        failed = int(row["failed_top_level_runs"] or 0)
        return {
            "agent_runs": int(row["agent_runs"] or 0),
            "direct_agent_runs": int(row["direct_agent_runs"] or 0),
            "network_agent_runs": int(row["network_agent_runs"] or 0),
            "network_runs": int(row["network_runs"] or 0),
            "active_top_level_runs": int(row["active_top_level_runs"] or 0),
            "failed_top_level_runs": failed,
            "top_level_runs": top_level,
            "failure_rate_percent": (
                round((failed / top_level) * 100, 2) if top_level else 0.0
            ),
            "p95_top_level_latency_ms": _rounded(
                row["p95_top_level_latency_ms"]
            ),
            "avg_agent_runs_per_network_run": _rounded(
                row["avg_agent_runs_per_network_run"]
            ),
        }

    async def _direct_runs(
        self,
        session: AsyncSession,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if params["network_id"] is not None:
            return []
        statement = text(
            """
            SELECT
                run.id,
                run.trace_id,
                run.project_id,
                run.agent_id,
                agent.name AS agent_name,
                run.session_id,
                run.network_execution_id,
                run.network_invocation_id,
                run.parent_run_id,
                run.environment,
                run.origin,
                run.status,
                run.input_message,
                run.usage,
                run.result,
                run.failure_code,
                run.failure_detail,
                run.started_at,
                run.completed_at,
                run.created_at
            FROM agent.agent_runs AS run
            JOIN agent.agents AS agent
              ON agent.id = run.agent_id
             AND agent.project_id = run.project_id
            WHERE run.project_id = :project_id
              AND run.network_execution_id IS NULL
            ORDER BY
                COALESCE(run.started_at, run.created_at) DESC,
                run.id DESC
            LIMIT :limit
            """
        )
        rows = (await session.execute(statement, params)).mappings().all()
        return [_agent_run(row) for row in rows]

    async def _network_runs(
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
                execution.network_version_id,
                version.version AS network_version,
                execution.network_session_id,
                network_session.environment,
                execution.status,
                execution.input_message,
                execution.output_message,
                execution.root_trace_id,
                execution.failure_code,
                execution.failure_detail,
                execution.draft_revision,
                execution.started_at,
                execution.completed_at,
                execution.created_at,
                CASE
                    WHEN execution.started_at IS NOT NULL
                     AND execution.completed_at IS NOT NULL
                    THEN EXTRACT(
                        EPOCH FROM (
                            execution.completed_at - execution.started_at
                        )
                    ) * 1000
                    ELSE NULL
                END AS duration_ms
            FROM network.network_executions AS execution
            JOIN network.networks AS network
              ON network.id = execution.network_id
             AND network.project_id = execution.project_id
            JOIN network.network_sessions AS network_session
              ON network_session.id = execution.network_session_id
            LEFT JOIN network.network_versions AS version
              ON version.id = execution.network_version_id
            WHERE execution.project_id = :project_id
              AND (
                :network_id IS NULL
                OR execution.network_id = :network_id
              )
            ORDER BY execution.created_at DESC, execution.id DESC
            LIMIT :limit
            """
        )
        rows = (await session.execute(statement, params)).mappings().all()
        return [
            {
                "id": str(row["id"]),
                "network_id": str(row["network_id"]),
                "network_name": str(row["network_name"]),
                "network_version_id": (
                    str(row["network_version_id"])
                    if row["network_version_id"]
                    else None
                ),
                "network_version": row["network_version"],
                "network_session_id": str(row["network_session_id"]),
                "environment": str(row["environment"]),
                "status": str(row["status"]),
                "input_message": str(row["input_message"]),
                "output_message": row["output_message"],
                "root_trace_id": (
                    str(row["root_trace_id"]) if row["root_trace_id"] else None
                ),
                "failure_code": row["failure_code"],
                "failure_detail": row["failure_detail"],
                "draft_revision": row["draft_revision"],
                "started_at": _iso(row["started_at"]),
                "completed_at": _iso(row["completed_at"]),
                "created_at": _iso(row["created_at"]),
                "duration_ms": _rounded(row["duration_ms"]),
                "agent_runs": [],
            }
            for row in rows
        ]

    async def _attach_child_runs(
        self,
        session: AsyncSession,
        network_runs: list[dict[str, Any]],
    ) -> None:
        if not network_runs:
            return

        execution_ids = [UUID(item["id"]) for item in network_runs]
        statement = text(
            """
            SELECT
                run.id,
                run.trace_id,
                run.project_id,
                run.agent_id,
                agent.name AS agent_name,
                run.session_id,
                run.network_execution_id,
                run.network_invocation_id,
                run.parent_run_id,
                run.environment,
                run.origin,
                run.status,
                run.input_message,
                run.usage,
                run.result,
                run.failure_code,
                run.failure_detail,
                run.started_at,
                run.completed_at,
                run.created_at
            FROM agent.agent_runs AS run
            JOIN agent.agents AS agent
              ON agent.id = run.agent_id
             AND agent.project_id = run.project_id
            WHERE run.network_execution_id IN :network_execution_ids
            ORDER BY
                COALESCE(run.started_at, run.created_at) ASC,
                run.id ASC
            """
        ).bindparams(bindparam("network_execution_ids", expanding=True))
        rows = (
            await session.execute(
                statement,
                {"network_execution_ids": execution_ids},
            )
        ).mappings().all()

        children: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            execution_id = row["network_execution_id"]
            if execution_id is None:
                continue
            children[str(execution_id)].append(_agent_run(row))

        for network_run in network_runs:
            network_run["agent_runs"] = children.get(network_run["id"], [])
