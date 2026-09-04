from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from modules.core.application.dtos.project_overview import (
    ProjectOverviewQuery,
    ProjectOverviewTrace,
)
from modules.core.application.use_cases.get_project_overview import (
    GetProjectOverviewUseCase,
)
from modules.core.infra.database.project_overview_reader import (
    SQLAlchemyProjectOverviewReader,
    _AGENT_ENVIRONMENT_CTE,
)
from modules.core.infra.database.uow_project_overview_reader import (
    UnitOfWorkProjectOverviewReader,
)
from modules.core.presentation.controllers.get_project_overview_controller import (
    GetProjectOverviewController,
)
from shared.presentation.contracts import OperationRequest


class FakeOverviewReader:
    def __init__(self) -> None:
        self.arguments: dict[str, Any] | None = None

    async def fetch(self, **kwargs: Any) -> dict[str, Any]:
        self.arguments = kwargs
        return {
            "summary": {
                "active_agents": 0,
                "production_agents": 0,
                "requests": 0,
                "request_change_percent": 0.0,
                "avg_latency_ms": None,
                "p95_latency_ms": None,
                "success_rate": None,
                "failed_requests": 0,
                "cost_usd": 0.0,
                "unknown_cost_count": 0,
            },
            "timeseries": [],
            "environment_distribution": {
                "draft": 0,
                "staging": 0,
                "production": 0,
            },
            "recent_releases": [],
            "recent_traces": [],
            "knowledge_summary": {
                "collections": 0,
                "documents": 0,
                "indexed_documents": 0,
                "failed_documents": 0,
                "storage_bytes": 0,
                "pending_documents": 0,
            },
            "tools_summary": {
                "total": 0,
                "active": 0,
                "inactive": 0,
                "recent_failures": [],
            },
            "capabilities": {
                "sessions_jobs": False,
                "ingestion_pipeline": False,
                "activity_feed": False,
            },
        }


def test_query_defaults_to_24_hours_and_hour_bucket() -> None:
    query = ProjectOverviewQuery(project_id=uuid4())

    assert query.from_ is not None
    assert query.to is not None
    assert query.bucket == "hour"
    assert query.to - query.from_ == timedelta(hours=24)
    assert query.from_.tzinfo is not None


def test_query_uses_day_bucket_for_seven_day_window() -> None:
    end = datetime(2026, 6, 19, tzinfo=UTC)
    query = ProjectOverviewQuery(
        project_id=uuid4(),
        **{"from": end - timedelta(days=7), "to": end},
    )

    assert query.bucket == "day"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "from": datetime(2026, 1, 1, tzinfo=UTC),
            "to": datetime(2026, 2, 1, tzinfo=UTC),
        },
        {
            "from": datetime(2026, 6, 19, tzinfo=UTC),
            "to": datetime(2026, 6, 18, tzinfo=UTC),
        },
        {
            "from": datetime(2026, 6, 1),
            "to": datetime(2026, 6, 2),
        },
        {
            "from": datetime(2026, 6, 1, tzinfo=UTC),
            "to": datetime(2026, 6, 9, tzinfo=UTC),
            "bucket": "hour",
        },
    ],
)
def test_query_rejects_invalid_windows(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ProjectOverviewQuery(project_id=uuid4(), **payload)


def test_recent_trace_accepts_playground_execution_context() -> None:
    trace = ProjectOverviewTrace(
        id=uuid4(),
        environment="playground",
        status="completed",
        cost_known=False,
    )

    assert trace.environment == "playground"


def test_overview_environment_cte_ignores_archived_releases() -> None:
    assert "release.status IN ('production', 'staging', 'draft')" in _AGENT_ENVIRONMENT_CTE
    assert "WHEN 'production' THEN 3" in _AGENT_ENVIRONMENT_CTE
    assert "WHEN 'staging' THEN 2" in _AGENT_ENVIRONMENT_CTE
    assert "current_release.environment" in _AGENT_ENVIRONMENT_CTE
    assert "release.status = 'production'" not in _AGENT_ENVIRONMENT_CTE


def test_uow_environment_cte_matches_live_release_resolution() -> None:
    cte = UnitOfWorkProjectOverviewReader._agent_environment_cte()

    assert "release.status IN ('production', 'staging', 'draft')" in cte
    assert "WHEN 'production' THEN 3" in cte
    assert "WHEN 'staging' THEN 2" in cte
    assert "current_release.environment" in cte


def test_recent_releases_filter_tab_and_dedupe_current_slots() -> None:
    source = inspect.getsource(SQLAlchemyProjectOverviewReader._recent_releases)

    assert "release.status IN ('draft', 'staging', 'production')" in source
    assert "release.status = :environment" in source
    assert "PARTITION BY release.agent_id, release.status" in source
    assert "WHERE status_rank = 1" in source
    assert "ELSE 'draft'" not in source


@pytest.mark.asyncio
async def test_use_case_returns_zero_state_without_fabricated_capabilities() -> None:
    reader = FakeOverviewReader()
    use_case = GetProjectOverviewUseCase(reader)
    query = ProjectOverviewQuery(project_id=uuid4())

    output = await use_case.execute(query)

    assert output.summary.requests == 0
    assert output.summary.success_rate is None
    assert output.summary.cost_usd == 0.0
    assert output.capabilities.sessions_jobs is False
    assert output.capabilities.ingestion_pipeline is False
    assert output.capabilities.activity_feed is False
    assert reader.arguments is not None
    assert reader.arguments["project_id"] == query.project_id
    assert reader.arguments["environment"] == "all"


@pytest.mark.asyncio
async def test_controller_parses_raw_query_and_sets_private_cache_headers() -> None:
    reader = FakeOverviewReader()
    controller = GetProjectOverviewController(GetProjectOverviewUseCase(reader))
    project_id = uuid4()
    response = await controller.handle(
        OperationRequest(
            path_params={"project_id": str(project_id)},
            query_params={
                "from": "2026-06-18T00:00:00Z",
                "to": "2026-06-19T00:00:00Z",
                "bucket": "hour",
                "environment": "production",
                "recent_limit": "10",
                "ignored": "value",
            },
        )
    )

    assert response.outcome == "success"
    assert response.metadata["Cache-Control"] == "private, max-age=15"
    assert response.metadata["Vary"] == "Authorization"
    assert response.body["data"]["project_id"] == str(project_id)
    assert response.body["data"]["from"] == "2026-06-18T00:00:00Z"
    assert reader.arguments is not None
    assert reader.arguments["environment"] == "production"
    assert reader.arguments["recent_limit"] == 10
