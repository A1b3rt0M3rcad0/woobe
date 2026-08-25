from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from modules.network.infra.database.run_diagnostics_reader import (
    build_network_run_diagnostics,
)


def _run(
    *,
    run_id,
    parent_run_id,
    started_at,
    completed_at,
    diagnostics,
    usage,
    tools=None,
    sources=None,
    fallback=False,
):
    return SimpleNamespace(
        id=run_id,
        parent_run_id=parent_run_id,
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
        usage=usage,
        result={
            "diagnostics": diagnostics,
            "tool_calls": tools or [],
            "sources": sources or [],
            "fallback_used": fallback,
            "llm_calls": [{} for _ in range(int(diagnostics.get("llm_call_count") or 0))],
            "cost_status": diagnostics.get("cost_status"),
            "cost_usd": usage.get("cost_usd"),
        },
    )


def _invocation(*, invocation_id, parent_id, depth):
    return SimpleNamespace(
        id=invocation_id,
        parent_invocation_id=parent_id,
        depth=depth,
    )


def test_network_run_diagnostics_aggregate_canonical_agent_run_v5_metrics():
    started_at = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    execution = SimpleNamespace(
        id=uuid4(),
        status="completed",
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=10),
    )
    root_id = uuid4()
    child_id = uuid4()

    root = _run(
        run_id=root_id,
        parent_run_id=None,
        started_at=started_at + timedelta(seconds=1),
        completed_at=started_at + timedelta(seconds=9),
        diagnostics={
            "schema_version": 5,
            "llm_work_latency_ms": 7000,
            "tool_work_latency_ms": 600,
            "prepare_latency_ms": 100,
            "finalization_work_latency_ms": 0,
            "orchestration_latency_ms": None,
            "llm_call_count": 2,
            "usage_complete": True,
            "cost_status": "known",
            "cost_usd": 0.00047281,
            "source_count": 1,
            "fallback_used": False,
        },
        usage={
            "input_tokens": 500,
            "output_tokens": 50,
            "total_tokens": 550,
            "cost_usd": 0.00047281,
        },
        tools=[
            {
                "tool_name": "delegate_to_researcher",
                "duration_ms": 5000,
                "success": True,
            },
            {
                "tool_name": "search_web",
                "duration_ms": 600,
                "success": True,
            },
        ],
        sources=[{"chunk_id": "root"}],
    )
    child = _run(
        run_id=child_id,
        parent_run_id=root_id,
        started_at=started_at + timedelta(seconds=3),
        completed_at=started_at + timedelta(seconds=8),
        diagnostics={
            "schema_version": 5,
            "llm_work_latency_ms": 4000,
            "tool_work_latency_ms": 200,
            "prepare_latency_ms": 80,
            "finalization_work_latency_ms": 0,
            "orchestration_latency_ms": None,
            "llm_call_count": 1,
            "usage_complete": False,
            "cost_status": "unknown_pricing",
            "cost_usd": None,
            "source_count": 2,
            "fallback_used": True,
        },
        usage={
            "input_tokens": 300,
            "output_tokens": 60,
            "total_tokens": 360,
            "cost_usd": None,
        },
        tools=[
            {
                "tool_name": "db_query",
                "duration_ms": 200,
                "success": False,
            }
        ],
        sources=[{"chunk_id": "a"}, {"chunk_id": "b"}],
        fallback=True,
    )

    result = build_network_run_diagnostics(
        execution=execution,
        invocations=[
            _invocation(invocation_id=root_id, parent_id=None, depth=0),
            _invocation(invocation_id=child_id, parent_id=root_id, depth=1),
        ],
        agent_runs=[root, child],
    )

    assert result["network_wall_latency_ms"] == 10000
    assert result["agent_work_latency_ms"] == 8000
    assert result["llm_runtime_latency_ms"] == 11000
    assert result["tool_work_latency_ms"] == 800
    assert result["agent_run_count"] == 2
    assert result["delegation_count"] == 1
    assert result["max_depth"] == 2
    assert result["max_fan_out"] == 1
    assert result["llm_call_count"] == 3
    assert result["tool_call_count"] == 2
    assert result["successful_tool_calls"] == 1
    assert result["failed_tool_calls"] == 1
    assert result["prepare_latency_ms"] == 180
    assert result["persistence_latency_ms"] == 0
    assert result["orchestration_latency_ms"] is None
    assert result["input_tokens"] == 800
    assert result["output_tokens"] == 110
    assert result["total_tokens"] == 910
    assert result["usage_complete"] is False
    assert result["cost_usd"] == 0.00047281
    assert result["cost_status"] == "partial"
    assert result["fallback_count"] == 1
    assert result["source_count"] == 3
    assert result["telemetry_status"] == "complete"


def test_network_run_diagnostics_preserve_real_parallel_agent_work():
    started_at = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    execution = SimpleNamespace(
        id=uuid4(),
        status="completed",
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=10),
    )
    root_id = uuid4()
    child_a_id = uuid4()
    child_b_id = uuid4()
    empty_diagnostics = {
        "schema_version": 5,
        "llm_work_latency_ms": 0,
        "tool_work_latency_ms": 0,
        "prepare_latency_ms": 0,
        "finalization_work_latency_ms": 0,
        "llm_call_count": 0,
        "usage_complete": True,
        "cost_status": "known",
        "cost_usd": 0,
    }
    empty_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0,
    }
    runs = [
        _run(
            run_id=root_id,
            parent_run_id=None,
            started_at=started_at,
            completed_at=started_at + timedelta(seconds=10),
            diagnostics=empty_diagnostics,
            usage=empty_usage,
        ),
        _run(
            run_id=child_a_id,
            parent_run_id=root_id,
            started_at=started_at + timedelta(seconds=2),
            completed_at=started_at + timedelta(seconds=7),
            diagnostics=empty_diagnostics,
            usage=empty_usage,
        ),
        _run(
            run_id=child_b_id,
            parent_run_id=root_id,
            started_at=started_at + timedelta(seconds=4),
            completed_at=started_at + timedelta(seconds=9),
            diagnostics=empty_diagnostics,
            usage=empty_usage,
        ),
    ]

    result = build_network_run_diagnostics(
        execution=execution,
        invocations=[
            _invocation(invocation_id=root_id, parent_id=None, depth=0),
            _invocation(invocation_id=child_a_id, parent_id=root_id, depth=1),
            _invocation(invocation_id=child_b_id, parent_id=root_id, depth=1),
        ],
        agent_runs=runs,
    )

    assert result["network_wall_latency_ms"] == 10000
    assert result["agent_work_latency_ms"] == 13000
    assert result["delegation_count"] == 2
    assert result["max_fan_out"] == 2
    assert result["telemetry_status"] == "complete"


def test_network_run_diagnostics_use_first_agent_run_when_durable_start_is_absent():
    started_at = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    completed_at = started_at + timedelta(milliseconds=900)
    execution = SimpleNamespace(
        id=uuid4(),
        status="completed",
        started_at=None,
        completed_at=completed_at,
    )
    run_id = uuid4()
    run = _run(
        run_id=run_id,
        parent_run_id=None,
        started_at=started_at,
        completed_at=completed_at,
        diagnostics={
            "schema_version": 5,
            "llm_work_latency_ms": 500,
            "tool_work_latency_ms": 0,
            "prepare_latency_ms": 10,
            "finalization_work_latency_ms": 0,
            "llm_call_count": 1,
            "usage_complete": True,
            "cost_status": "known",
            "cost_usd": 0.001,
        },
        usage={
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "cost_usd": 0.001,
        },
    )

    result = build_network_run_diagnostics(
        execution=execution,
        invocations=[_invocation(invocation_id=run_id, parent_id=None, depth=0)],
        agent_runs=[run],
    )

    assert result["network_wall_latency_ms"] == 900
    assert result["telemetry_status"] == "complete"
