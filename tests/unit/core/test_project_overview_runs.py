from __future__ import annotations

import inspect
from datetime import UTC, datetime
from uuid import uuid4

from modules.core.application.dtos.project_overview import (
    ProjectOverviewNetworkRun,
    ProjectOverviewSummary,
    ProjectOverviewTimeseriesPoint,
)
from modules.core.infra.database.active_project_overview_reader import (
    ActiveDocumentProjectOverviewReader,
)


def test_run_summary_keeps_legacy_fields_compatible() -> None:
    summary = ProjectOverviewSummary(
        agent_runs=12,
        direct_agent_runs=7,
        network_agent_runs=5,
        network_runs=3,
        avg_agent_run_duration_ms=125.0,
        avg_network_run_duration_ms=800.0,
        requests=12,
        avg_latency_ms=125.0,
    )

    assert summary.agent_runs == summary.requests
    assert summary.direct_agent_runs + summary.network_agent_runs == summary.agent_runs
    assert summary.avg_agent_run_duration_ms == summary.avg_latency_ms


def test_timeseries_projection_exposes_agent_run_fields() -> None:
    point = {
        "requests": 9,
        "success": 7,
        "failed": 2,
        "avg_latency_ms": 160.5,
        "p95_latency_ms": 410.0,
    }

    ActiveDocumentProjectOverviewReader._apply_agent_run_timeseries_projection(point)

    assert point["agent_runs"] == 9
    assert point["agent_run_success"] == 7
    assert point["agent_run_failed"] == 2
    assert point["avg_agent_run_duration_ms"] == 160.5
    assert point["p95_agent_run_duration_ms"] == 410.0


def test_network_run_contract_preserves_operational_identity() -> None:
    run = ProjectOverviewNetworkRun(
        id=uuid4(),
        network_id=uuid4(),
        network_name="Support Network",
        environment="production",
        status="completed",
        duration_ms=950.0,
        started_at=datetime.now(UTC),
    )

    assert run.network_name == "Support Network"
    assert run.environment == "production"
    assert run.duration_ms == 950.0


def test_timeseries_contract_separates_run_types() -> None:
    point = ProjectOverviewTimeseriesPoint(
        bucket_start=datetime.now(UTC),
        agent_runs=18,
        network_runs=4,
        avg_agent_run_duration_ms=220.0,
        avg_network_run_duration_ms=1300.0,
    )

    assert point.agent_runs == 18
    assert point.network_runs == 4
    assert point.avg_agent_run_duration_ms != point.avg_network_run_duration_ms


def test_reader_aggregates_network_runs_from_network_execution_domain() -> None:
    source = inspect.getsource(ActiveDocumentProjectOverviewReader)

    assert "network.network_executions" in source
    assert "network.network_invocations" in source
    assert "avg_agent_runs_per_network_run" in source
    assert "observability.traces" in source
