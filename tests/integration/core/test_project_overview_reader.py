from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from modules.core.infra.database.contextual_project_overview_reader import (
    ContextualProjectOverviewReader,
)
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.infra.config import Settings


_PROJECT_INSERT = text(
    """
    INSERT INTO core.projects (
        id, workspace_id, name, slug, status, data
    ) VALUES (
        :id, :workspace_id, :name, :slug, 'active', CAST(:data AS jsonb)
    )
    """
)

_AGENT_INSERT = text(
    """
    INSERT INTO agent.agents (
        id, project_id, name, description, type, system_prompt,
        provider, model, session_mode, status, settings
    ) VALUES (
        :id, :project_id, :name, '', 'assistant', '',
        'openai', 'test-model', 'stateless', :status, CAST(:settings AS jsonb)
    )
    """
)

_RELEASE_INSERT = text(
    """
    INSERT INTO agent.agent_releases (
        id, project_id, agent_id, version, status, promoted_at,
        session_mode, snapshot_kind
    ) VALUES (
        :id, :project_id, :agent_id, :version, :status, :promoted_at,
        :session_mode, :snapshot_kind
    )
    """
)

_TRACE_INSERT = text(
    """
    INSERT INTO observability.traces (
        id, project_id, agent_id, status, started_at, ended_at,
        total_latency_ms, total_cost_usd, fallback_used, data
    ) VALUES (
        :id, :project_id, :agent_id, :status, :started_at, :ended_at,
        :total_latency_ms, :total_cost_usd, false, CAST(:data AS jsonb)
    )
    """
)


async def _cleanup(
    session_factory: async_sessionmaker[AsyncSession],
    project_id: UUID,
    other_project_id: UUID,
) -> None:
    params = {"project_id": project_id, "other_project_id": other_project_id}
    async with session_factory() as session:
        await session.execute(
            text(
                "DELETE FROM observability.trace_events "
                "WHERE project_id IN (:project_id, :other_project_id)"
            ),
            params,
        )
        await session.execute(
            text(
                "DELETE FROM observability.traces "
                "WHERE project_id IN (:project_id, :other_project_id)"
            ),
            params,
        )
        await session.execute(
            text(
                "DELETE FROM agent.agent_releases "
                "WHERE project_id IN (:project_id, :other_project_id)"
            ),
            params,
        )
        await session.execute(
            text(
                "DELETE FROM agent.agents "
                "WHERE project_id IN (:project_id, :other_project_id)"
            ),
            params,
        )
        await session.execute(
            text(
                "DELETE FROM core.projects "
                "WHERE id IN (:project_id, :other_project_id)"
            ),
            params,
        )
        await session.commit()


@pytest.mark.asyncio
async def test_project_overview_aggregates_filters_and_isolates_projects() -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    project_id = uuid4()
    other_project_id = uuid4()
    workspace_id = uuid4()
    prod_agent_id = uuid4()
    staging_agent_id = uuid4()
    draft_agent_id = uuid4()
    other_agent_id = uuid4()
    start = datetime(2026, 6, 18, tzinfo=UTC)
    end = start + timedelta(days=1)

    prod_completed_id = uuid4()
    prod_failed_id = uuid4()
    staging_completed_id = uuid4()
    current_trace_ids = {
        prod_completed_id,
        prod_failed_id,
        staging_completed_id,
    }

    try:
        async with session_factory() as session:
            await session.execute(
                _PROJECT_INSERT,
                [
                    {
                        "id": project_id,
                        "workspace_id": workspace_id,
                        "name": "Overview fixture",
                        "slug": f"overview-{project_id.hex[:12]}",
                        "data": "{}",
                    },
                    {
                        "id": other_project_id,
                        "workspace_id": workspace_id,
                        "name": "Isolation fixture",
                        "slug": f"isolation-{other_project_id.hex[:12]}",
                        "data": "{}",
                    },
                ],
            )
            await session.execute(
                _AGENT_INSERT,
                [
                    {
                        "id": prod_agent_id,
                        "project_id": project_id,
                        "name": "Production agent",
                        "status": "active",
                        "settings": "{}",
                    },
                    {
                        "id": staging_agent_id,
                        "project_id": project_id,
                        "name": "Staging agent",
                        "status": "active",
                        "settings": "{}",
                    },
                    {
                        "id": draft_agent_id,
                        "project_id": project_id,
                        "name": "Draft agent",
                        "status": "active",
                        "settings": "{}",
                    },
                    {
                        "id": other_agent_id,
                        "project_id": other_project_id,
                        "name": "Other project agent",
                        "status": "active",
                        "settings": "{}",
                    },
                ],
            )
            await session.execute(
                _RELEASE_INSERT,
                [
                    {
                        "id": uuid4(),
                        "project_id": project_id,
                        "agent_id": prod_agent_id,
                        "version": "1.0.0",
                        "status": "production",
                        "promoted_at": start - timedelta(days=1),
                        "session_mode": "stateless",
                        "snapshot_kind": "release",
                    },
                    {
                        "id": uuid4(),
                        "project_id": project_id,
                        "agent_id": staging_agent_id,
                        "version": "1.0.0-rc1",
                        "status": "staging",
                        "promoted_at": start - timedelta(days=1),
                        "session_mode": "stateless",
                        "snapshot_kind": "staging",
                    },
                    {
                        "id": uuid4(),
                        "project_id": other_project_id,
                        "agent_id": other_agent_id,
                        "version": "9.9.9",
                        "status": "production",
                        "promoted_at": start - timedelta(days=1),
                        "session_mode": "stateless",
                        "snapshot_kind": "release",
                    },
                ],
            )
            await session.execute(
                _TRACE_INSERT,
                [
                    {
                        "id": prod_completed_id,
                        "project_id": project_id,
                        "agent_id": prod_agent_id,
                        "status": "completed",
                        "started_at": start + timedelta(minutes=30),
                        "ended_at": start + timedelta(minutes=31),
                        "total_latency_ms": 100.0,
                        "total_cost_usd": 0.25,
                        "data": json.dumps(
                            {
                                "input_tokens": 10,
                                "output_tokens": 5,
                                "total_tokens": 15,
                            }
                        ),
                    },
                    {
                        "id": prod_failed_id,
                        "project_id": project_id,
                        "agent_id": prod_agent_id,
                        "status": "failed",
                        "started_at": start + timedelta(hours=1, minutes=30),
                        "ended_at": start + timedelta(hours=1, minutes=31),
                        "total_latency_ms": 300.0,
                        "total_cost_usd": None,
                        "data": json.dumps(
                            {
                                "input_tokens": 4,
                                "output_tokens": 1,
                                "total_tokens": 5,
                            }
                        ),
                    },
                    {
                        "id": staging_completed_id,
                        "project_id": project_id,
                        "agent_id": staging_agent_id,
                        "status": "completed",
                        "started_at": start + timedelta(hours=2, minutes=30),
                        "ended_at": start + timedelta(hours=2, minutes=31),
                        "total_latency_ms": 50.0,
                        "total_cost_usd": 0.10,
                        "data": json.dumps(
                            {
                                "input_tokens": 8,
                                "output_tokens": 2,
                                "total_tokens": 10,
                            }
                        ),
                    },
                    {
                        "id": uuid4(),
                        "project_id": project_id,
                        "agent_id": prod_agent_id,
                        "status": "running",
                        "started_at": start + timedelta(hours=3),
                        "ended_at": None,
                        "total_latency_ms": None,
                        "total_cost_usd": None,
                        "data": "{}",
                    },
                    {
                        "id": uuid4(),
                        "project_id": project_id,
                        "agent_id": prod_agent_id,
                        "status": "completed",
                        "started_at": start - timedelta(hours=1),
                        "ended_at": start - timedelta(minutes=59),
                        "total_latency_ms": 80.0,
                        "total_cost_usd": 0.05,
                        "data": "{}",
                    },
                    {
                        "id": uuid4(),
                        "project_id": other_project_id,
                        "agent_id": other_agent_id,
                        "status": "completed",
                        "started_at": start + timedelta(minutes=15),
                        "ended_at": start + timedelta(minutes=16),
                        "total_latency_ms": 10.0,
                        "total_cost_usd": 9.99,
                        "data": json.dumps({"total_tokens": 999}),
                    },
                ],
            )
            await session.commit()

        statements: list[str] = []

        def capture_statement(
            _conn: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            statements.append(statement)

        event.listen(engine.sync_engine, "before_cursor_execute", capture_statement)
        try:
            uow = CoreUnitOfWork(engine)
            async with uow:
                reader = ContextualProjectOverviewReader(uow)
                expected_query_count = reader.query_count
                await uow.session.execute(
                    text("SET LOCAL TIME ZONE 'America/Sao_Paulo'")
                )
                statements.clear()
                overview = await reader.fetch(
                    project_id=project_id,
                    start=start,
                    end=end,
                    bucket="hour",
                    environment="all",
                    recent_limit=20,
                )
                query_count = len(statements)

                statements.clear()
                production = await reader.fetch(
                    project_id=project_id,
                    start=start,
                    end=end,
                    bucket="hour",
                    environment="production",
                    recent_limit=20,
                )
                production_query_count = len(statements)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", capture_statement)

        assert query_count == expected_query_count
        assert production_query_count == expected_query_count

        summary = overview["summary"]
        assert summary["active_agents"] == 3
        assert summary["production_agents"] == 1
        assert summary["requests"] == 4
        assert summary["request_change_percent"] == 300.0
        assert summary["avg_latency_ms"] == 150.0
        assert summary["p95_latency_ms"] == 280.0
        assert summary["success_rate"] == 66.67
        assert summary["failed_requests"] == 1
        assert summary["cost_usd"] == 0.35
        assert summary["unknown_cost_count"] == 1

        assert overview["environment_distribution"] == {
            "draft": 1,
            "staging": 1,
            "production": 1,
        }
        assert len(overview["timeseries"]) == 24
        assert overview["timeseries"][0]["bucket_start"].astimezone(UTC) == start
        assert sum(point["requests"] for point in overview["timeseries"]) == 4
        assert {trace["id"] for trace in overview["recent_traces"]} == current_trace_ids

        production_summary = production["summary"]
        assert production_summary["active_agents"] == 1
        assert production_summary["requests"] == 3
        assert production_summary["request_change_percent"] == 200.0
        assert production_summary["avg_latency_ms"] == 200.0
        assert production_summary["p95_latency_ms"] == 290.0
        assert production_summary["success_rate"] == 50.0
        assert production_summary["cost_usd"] == 0.25
        assert production_summary["unknown_cost_count"] == 1
        assert {trace["id"] for trace in production["recent_traces"]} == {
            prod_completed_id,
            prod_failed_id,
        }
    finally:
        await _cleanup(session_factory, project_id, other_project_id)
        await engine.dispose()
