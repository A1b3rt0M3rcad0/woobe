from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.infra.config import Settings


@pytest.mark.asyncio
async def test_project_overview_query_budget_index_and_p95() -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    project_id = uuid4()
    organization_id = uuid4()
    start = datetime(2026, 5, 20, tzinfo=UTC)
    end = start + timedelta(days=30)

    try:
        async with session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO core.projects (
                        id, organization_id, name, slug, status, data
                    ) VALUES (
                        :id, :organization_id, 'Performance fixture', :slug,
                        'active', '{}'::jsonb
                    )
                    """
                ),
                {
                    "id": project_id,
                    "organization_id": organization_id,
                    "slug": f"overview-perf-{project_id.hex[:12]}",
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO observability.traces (
                        id, project_id, agent_id, status, started_at, ended_at,
                        total_latency_ms, total_cost_usd, fallback_used, data
                    )
                    SELECT
                        CAST(
                            md5(:project_id_text || ':' || series::text)
                            AS uuid
                        ),
                        :project_id,
                        NULL,
                        CASE
                            WHEN series % 10 = 0 THEN 'failed'
                            ELSE 'completed'
                        END,
                        CAST(:start AS timestamptz)
                            + series * interval '14 minutes',
                        CAST(:start AS timestamptz)
                            + series * interval '14 minutes'
                            + interval '1 second',
                        50 + (series % 450),
                        CASE WHEN series % 7 = 0 THEN NULL ELSE 0.001 END,
                        false,
                        jsonb_build_object(
                            'input_tokens', series % 200,
                            'output_tokens', series % 80,
                            'total_tokens', (series % 200) + (series % 80)
                        )
                    FROM generate_series(0, 2999) AS series
                    """
                ),
                {
                    "project_id": project_id,
                    "project_id_text": str(project_id),
                    "start": start,
                },
            )
            await session.execute(text("ANALYZE observability.traces"))
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
            uow = CoreUnitOfWork(session_factory)
            async with uow:
                statements.clear()
                result = await uow.project_overview.fetch(
                    project_id=project_id,
                    start=start,
                    end=end,
                    bucket="day",
                    environment="all",
                    recent_limit=5,
                )
                query_count = len(statements)

                for _ in range(5):
                    await uow.project_overview.fetch(
                        project_id=project_id,
                        start=start,
                        end=end,
                        bucket="day",
                        environment="all",
                        recent_limit=5,
                    )

                durations: list[float] = []
                for _ in range(100):
                    began = perf_counter()
                    await uow.project_overview.fetch(
                        project_id=project_id,
                        start=start,
                        end=end,
                        bucket="day",
                        environment="all",
                        recent_limit=5,
                    )
                    durations.append(perf_counter() - began)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", capture_statement)

        assert query_count == 7
        assert result["summary"]["requests"] == 3000
        assert len(result["timeseries"]) == 30

        ordered = sorted(durations)
        p95_seconds = ordered[math.ceil(len(ordered) * 0.95) - 1]
        assert p95_seconds < 0.5, (
            f"overview p95 was {p95_seconds * 1000:.2f} ms"
        )

        async with session_factory() as session:
            await session.execute(text("SET LOCAL enable_seqscan = off"))
            plan_result = await session.execute(
                text(
                    """
                    EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                    SELECT COUNT(*)
                    FROM observability.traces
                    WHERE project_id = :project_id
                      AND started_at >= :start
                      AND started_at < :end
                      AND status IN ('completed', 'failed', 'cancelled')
                    """
                ),
                {"project_id": project_id, "start": start, "end": end},
            )
            plan = plan_result.scalar_one()
            serialized_plan = json.dumps(plan, default=str)
            assert (
                "ix_observability_traces_project_started_terminal"
                in serialized_plan
            )
    finally:
        async with session_factory() as session:
            await session.execute(
                text(
                    "DELETE FROM observability.traces "
                    "WHERE project_id = :project_id"
                ),
                {"project_id": project_id},
            )
            await session.execute(
                text("DELETE FROM core.projects WHERE id = :project_id"),
                {"project_id": project_id},
            )
            await session.commit()
        await engine.dispose()
