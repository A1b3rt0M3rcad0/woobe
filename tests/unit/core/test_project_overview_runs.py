from __future__ import annotations

import inspect
from datetime import UTC, datetime
from uuid import uuid4

from modules.core.application.dtos.project_overview import (
    ProjectOverviewChange,
    ProjectOverviewNetworkRelease,
    ProjectOverviewNetworkRun,
    ProjectOverviewOperationalIssues,
    ProjectOverviewSummary,
    ProjectOverviewTimeseriesPoint,
)
from modules.core.infra.database.active_project_overview_reader import (
    ActiveDocumentProjectOverviewReader,
)
from modules.core.infra.database.contextual_project_overview_reader import (
    ContextualProjectOverviewReader,
)


def test_run_summary_keeps_breakdown_and_legacy_fields_compatible() -> None:
    summary = ProjectOverviewSummary(
        agent_runs=12,
        direct_agent_runs=7,
        network_agent_runs=5,
        terminal_agent_runs=12,
        successful_agent_runs=11,
        failed_agent_runs=1,
        agent_run_success_rate=91.67,
        network_runs=3,
        avg_agent_run_duration_ms=125.0,
        avg_network_run_duration_ms=800.0,
        requests=12,
        avg_latency_ms=125.0,
    )

    assert summary.agent_runs == summary.requests
    assert summary.direct_agent_runs + summary.network_agent_runs == summary.agent_runs
    assert summary.avg_agent_run_duration_ms == summary.avg_latency_ms
    assert summary.successful_agent_runs + summary.failed_agent_runs == summary.terminal_agent_runs


def test_network_run_contract_exposes_real_cost_completeness() -> None:
    run = ProjectOverviewNetworkRun(
        id=uuid4(),
        network_id=uuid4(),
        network_name="Support Network",
        environment="production",
        status="completed",
        duration_ms=950.0,
        cost_usd=0.004,
        cost_known=False,
        priced_agent_runs=2,
        total_agent_runs=3,
        unknown_cost_count=1,
        started_at=datetime.now(UTC),
    )

    assert run.network_name == "Support Network"
    assert run.environment == "production"
    assert run.duration_ms == 950.0
    assert run.cost_usd == 0.004
    assert run.cost_known is False
    assert run.priced_agent_runs + run.unknown_cost_count == run.total_agent_runs


def test_timeseries_contract_separates_reliability_by_run_type() -> None:
    point = ProjectOverviewTimeseriesPoint(
        bucket_start=datetime.now(UTC),
        agent_runs=18,
        agent_run_success=16,
        agent_run_failed=1,
        agent_run_timed_out=1,
        agent_run_success_rate=88.89,
        network_runs=4,
        network_run_success=3,
        network_run_failed=1,
        network_run_success_rate=75.0,
        avg_agent_run_duration_ms=220.0,
        avg_network_run_duration_ms=1300.0,
    )

    assert point.agent_runs == 18
    assert point.network_runs == 4
    assert point.agent_run_success_rate != point.network_run_success_rate
    assert point.avg_agent_run_duration_ms != point.avg_network_run_duration_ms


def test_network_release_contract_preserves_change_context() -> None:
    release = ProjectOverviewNetworkRelease(
        id=uuid4(),
        network_id=uuid4(),
        network_name="Support Network",
        version="v2.1.0",
        environment="production",
        change_description="Updated routing and Agent bindings",
        activation_kind="publish",
        agent_count=4,
        created_at=datetime.now(UTC),
    )

    assert release.environment == "production"
    assert release.agent_count == 4
    assert release.change_description


def test_contextual_change_distinguishes_mutable_draft_from_release() -> None:
    change = ProjectOverviewChange(
        id=uuid4(),
        resource_type="network",
        resource_id=uuid4(),
        resource_name="Support Network",
        environment="draft",
        action="draft_updated",
        revision=14,
        occurred_at=datetime.now(UTC),
        immutable=False,
    )

    assert change.environment == "draft"
    assert change.action == "draft_updated"
    assert change.revision == 14
    assert change.immutable is False


def test_operational_issues_default_to_no_fabricated_findings() -> None:
    issues = ProjectOverviewOperationalIssues()

    assert issues.top_agent_failures == []
    assert issues.top_network_failures == []
    assert issues.top_failure_codes == []
    assert issues.failure_peak is None


def test_reader_uses_canonical_sources_without_overwriting_agent_breakdown() -> None:
    source = inspect.getsource(ActiveDocumentProjectOverviewReader)
    network_summary_source = inspect.getsource(
        ActiveDocumentProjectOverviewReader._network_summary
    )

    assert "network.network_executions" in source
    assert "network.network_invocations" in source
    assert "observability.traces" in source
    assert "avg_agent_runs_per_network_run" in source
    assert '"network_agent_runs"' not in network_summary_source
    assert "recent_network_releases" in source
    assert "unknown_cost_count" in source
    assert "operational_issues" in source


def test_contextual_reader_sources_changes_from_real_versioned_state() -> None:
    source = inspect.getsource(ContextualProjectOverviewReader)

    assert "agent.agent_releases" in source
    assert "network.network_versions" in source
    assert "network.draft_revision" in source
    assert "draft_updated" in source
    assert "rolled_back" in source
    assert ":environment IN" not in source
    assert ":environment = 'all' OR :environment = 'draft'" in source
