"""Overview reads recorded cost, without repricing history or waiting for traces."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from modules.agent.infra.database.models import AgentModel, SessionModel
from modules.agent.infra.database.run_models import AgentRunModel
from modules.core.infra.database.contextual_project_overview_reader import (
    ContextualProjectOverviewReader,
)
from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkModel,
    NetworkSessionModel,
)
from modules.observability.infra.database.models import TraceModel
from shared.infra.config import Settings


@pytest.fixture
async def recorded_runs():
    engine = create_async_engine(Settings().database_url)
    now = datetime.now(UTC)
    project_id = uuid4()
    async with AsyncSession(engine) as session:
        try:
            await session.execute(
                text(
                    "INSERT INTO core.projects(id,workspace_id,name,slug,status,data) VALUES(:id,:workspace,'Cost fixture',:slug,'active','{}'::jsonb)"
                ),
                {
                    "id": project_id,
                    "workspace": uuid4(),
                    "slug": "cost-" + project_id.hex,
                },
            )
            agent = AgentModel(
                project_id=project_id,
                name="Priced Agent",
                type="assistant",
                provider="custom",
                model="fixture",
            )
            session.add(agent)
            await session.flush()
            agent_session = SessionModel(project_id=project_id, agent_id=agent.id)
            network = NetworkModel(project_id=project_id, name="Cost Network")
            session.add_all([agent_session, network])
            await session.flush()
            network_session = NetworkSessionModel(
                project_id=project_id, network_id=network.id, environment="draft"
            )
            session.add(network_session)
            await session.flush()
            execution = NetworkExecutionModel(
                project_id=project_id,
                network_id=network.id,
                network_session_id=network_session.id,
                input_message="fixture",
                draft_revision=0,
                definition_snapshot={},
                resolved_bindings_snapshot={},
                status="completed",
                created_at=now,
                started_at=now,
                completed_at=now + timedelta(seconds=1),
            )
            session.add(execution)
            await session.flush()

            def add_run(
                *,
                cost,
                environment="production",
                status="completed",
                network_run=False,
                cost_status="known",
                with_trace=False,
                trace_cost=None,
                age=timedelta(),
            ):
                run = AgentRunModel(
                    project_id=project_id,
                    agent_id=agent.id,
                    session_id=agent_session.id,
                    trace_id=uuid4(),
                    environment=environment,
                    origin="runtime_api",
                    status=status,
                    input_message="fixture",
                    execution_snapshot={},
                    network_execution_id=execution.id if network_run else None,
                    started_at=now - age,
                    completed_at=now - age + timedelta(seconds=1),
                    usage={
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                        "cost_usd": cost,
                    },
                    result={
                        "diagnostics": {
                            "cost_status": cost_status,
                            "cost_reason": "Missing frozen price"
                            if cost_status == "unknown_pricing"
                            else None,
                        }
                    },
                )
                session.add(run)
                if with_trace:
                    # A stale trace even labels a constituent Run as standalone.
                    session.add(
                        TraceModel(
                            id=run.trace_id,
                            project_id=project_id,
                            agent_id=agent.id,
                            status="completed",
                            started_at=now,
                            total_cost_usd=trace_cost,
                            data={"execution_context": "staging", "total_tokens": 999},
                        )
                    )
                return run

            reader = ContextualProjectOverviewReader(SimpleNamespace(session=session))
            params = dict(
                project_id=project_id,
                start=now - timedelta(hours=1),
                end=now + timedelta(hours=1),
                previous_start=now - timedelta(hours=3),
                bucket="hour",
                step=timedelta(hours=1),
                environment="all",
                recent_limit=20,
            )
            yield session, reader, params, add_run, execution
        finally:
            await session.rollback()
            await engine.dispose()


@pytest.mark.asyncio
async def test_overview_uses_recorded_cost_and_causality_without_duplicate_traces(
    recorded_runs,
):
    session, reader, params, add_run, execution = recorded_runs
    direct = add_run(cost=0.2, with_trace=True)
    add_run(cost=0.1, environment="draft", network_run=True, with_trace=True)
    add_run(cost=0, environment="draft", network_run=True)
    add_run(
        cost=None,
        environment="draft",
        network_run=True,
        cost_status="unknown_pricing",
        with_trace=True,
        trace_cost=99,
    )
    failed = add_run(cost=0.05, status="failed")
    cancelled = add_run(cost=None, status="cancelled", cost_status="unknown_tokens")
    add_run(cost=0.9, status="running")
    add_run(cost=90, age=timedelta(hours=5))
    legacy = TraceModel(
        project_id=params["project_id"],
        status="completed",
        started_at=params["start"] + timedelta(minutes=1),
        total_cost_usd=0.03,
        data={},
    )
    foreign = TraceModel(
        project_id=uuid4(),
        status="completed",
        started_at=params["start"],
        total_cost_usd=100,
        data={},
    )
    session.add_all([legacy, foreign])
    await session.flush()

    summary = await reader._agent_run_summary(session, params)
    assert summary["agent_runs"] == 8
    assert summary["terminal_agent_runs"] == 7
    assert summary["direct_agent_runs"] == 5
    assert summary["network_agent_runs"] == 3
    assert summary["agent_run_cost_usd"] == pytest.approx(0.38)
    assert summary["priced_agent_runs"] == 5
    assert summary["unknown_agent_run_cost_count"] == 2
    assert summary["unknown_pricing_agent_runs"] == 1
    assert summary["unknown_token_usage_agent_runs"] == 1
    series = await reader._run_timeseries(session, params)
    assert sum(point["agent_runs"] for point in series) == 8
    assert sum(point["cost_usd"] or 0 for point in series) == pytest.approx(0.38)

    recent = await reader._recent_direct_agent_runs(session, params)
    assert {row["id"] for row in recent} == {
        direct.trace_id,
        failed.trace_id,
        cancelled.trace_id,
        legacy.id,
    }
    assert (
        next(row for row in recent if row["id"] == direct.trace_id)["total_tokens"]
        == 15
    )
    assert (
        next(row for row in recent if row["id"] == direct.trace_id)["environment"]
        == "production"
    )
    production = await reader._agent_run_summary(
        session, {**params, "environment": "production"}
    )
    assert production["agent_run_cost_usd"] == pytest.approx(0.25)
    network = (await reader._recent_network_runs(session, params))[0]
    assert network["id"] == execution.id
    assert network["total_agent_runs"] == 3
    assert network["priced_agent_runs"] == 2
    assert network["cost_usd"] == pytest.approx(0.1)
    assert network["cost_known"] is False
    assert network["unknown_cost_count"] == 1
    # Reading the corrected Overview does not rewrite the old trace.
    assert (await session.get(TraceModel, direct.trace_id)).total_cost_usd is None


@pytest.mark.asyncio
async def test_uncertain_run_is_terminal_with_unknown_cost_and_explicit_coverage(
    recorded_runs,
):
    session, reader, params, add_run, _ = recorded_runs
    run = add_run(cost=None, status="uncertain", cost_status="unknown_tokens")
    await session.flush()
    summary = await reader._agent_run_summary(session, params)
    assert summary["agent_runs"] == summary["terminal_agent_runs"] == 1
    assert summary["uncertain_agent_runs"] == 1
    assert summary["unknown_agent_run_cost_count"] == 1
    assert summary["agent_run_cost_usd"] is None
    assert summary["agent_run_success_rate"] == 0
    assert summary["agent_run_error_rate"] == 100
    recent = (await reader._recent_direct_agent_runs(session, params))[0]
    assert recent["id"] == run.trace_id
    assert recent["status"] == "uncertain"
    assert recent["cost_status"] == "unknown_tokens"
    series = await reader._run_timeseries(session, params)
    point = next(row for row in series if row["agent_runs"])
    assert point["agent_run_uncertain"] == 1
    assert point["unknown_cost_count"] == 1
    assert point["cost_usd"] is None


@pytest.mark.asyncio
async def test_network_cost_stays_partial_until_all_constituent_runs_are_terminal(
    recorded_runs,
):
    session, reader, params, add_run, _ = recorded_runs
    add_run(cost=0, environment="draft", network_run=True)
    add_run(cost=0.9, environment="draft", network_run=True, status="running")
    await session.flush()
    network = (await reader._recent_network_runs(session, params))[0]
    assert network["total_agent_runs"] == 2
    assert network["priced_agent_runs"] == 1
    assert network["unknown_cost_count"] == 1
    assert network["cost_usd"] == 0
    assert network["cost_known"] is False


@pytest.mark.asyncio
async def test_running_network_exposes_subtotal_without_claiming_final_cost(
    recorded_runs,
):
    session, reader, params, add_run, execution = recorded_runs
    execution.status = "running"
    execution.completed_at = None
    add_run(cost=0.1, environment="draft", network_run=True)
    await session.flush()
    network = (await reader._recent_network_runs(session, params))[0]
    assert network["cost_usd"] == pytest.approx(0.1)
    assert network["priced_agent_runs"] == 1
    assert network["cost_known"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cost,cost_status",
    [
        (None, "unknown_pricing"),
        (True, "known"),
        ("0.5", "known"),
        (-1, "known"),
        (0.5, "unknown_tokens"),
    ],
)
async def test_unknown_or_invalid_recorded_cost_is_not_replaced_by_stale_trace(
    recorded_runs, cost, cost_status
):
    session, reader, params, add_run, _ = recorded_runs
    run = add_run(cost=cost, cost_status=cost_status, with_trace=True, trace_cost=99)
    await session.flush()
    summary = await reader._agent_run_summary(session, params)
    assert summary["agent_runs"] == 1
    assert summary["agent_run_cost_usd"] is None
    assert summary["unknown_agent_run_cost_count"] == 1
    recent = (await reader._recent_direct_agent_runs(session, params))[0]
    assert recent["id"] == run.trace_id
    assert recent["cost_known"] is False
    assert recent["cost_status"] != "known"
    if cost_status == "unknown_pricing":
        assert recent["cost_status"] == "unknown_pricing"
        assert recent["cost_reason"] == "Missing frozen price"
