from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.infra.config import Settings


@pytest.mark.asyncio
async def test_project_overview_query_budget_and_index() -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    project_id = uuid4()
    workspace_id = uuid4()
    start = datetime(2026, 5, 20, tzinfo=UTC)
    end = start + timedelta(days=30)

    try:
        async with session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO core.projects (
                        id, workspace_id, name, slug, status, data
                    ) VALUES (
                        :id, :workspace_id, 'Performance fixture', :slug,
                        'active', '{}'::jsonb
                    )
                    """
                ),
                {
                    "id": project_id,
                    "workspace_id": workspace_id,
                    "slug": f"overview-perf-{project_id.hex[:12]}",
                },
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
            uow = CoreUnitOfWork(session_factory)
            async with uow:
                expected_query_count = uow.project_overview.query_count
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
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", capture_statement)

        assert query_count == expected_query_count
        assert result["summary"]["requests"] == 0
        assert len(result["timeseries"]) == 30

        async with session_factory() as session:
            await session.execute(text("SET LOCAL enable_seqscan = off"))
            plan_result = await session.execute(
                text(
                    """
                    EXPLAIN (FORMAT JSON)
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
            serialized_plan = json.dumps(plan_result.scalar_one(), default=str)
            assert "ix_observability_traces_project_started_terminal" in serialized_plan
    finally:
        async with session_factory() as session:
            await session.execute(
                text("DELETE FROM core.projects WHERE id = :project_id"),
                {"project_id": project_id},
            )
            await session.commit()
        await engine.dispose()
