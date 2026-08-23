from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from modules.network.infra.database.run_diagnostics_reader import (
    build_network_run_diagnostics,
)


def _trace(*, runtime_ms, diagnostics, tools, cost=None, fallback=False):
    return SimpleNamespace(
        id=uuid4(),
        total_latency_ms=runtime_ms,
        total_cost_usd=cost,
        fallback_used=fallback,
        data={
            "diagnostics": diagnostics,
            "tool_calls": tools,
        },
    )


def _event(event_type, invocation_id, created_at, payload=None):
    return SimpleNamespace(
        event_type=event_type,
        invocation_id=invocation_id,
        created_at=created_at,
        payload=payload or {},
    )


def test_network_run_diagnostics_exclude_nested_delegation_time_from_agent_work():
    started_at = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    execution = SimpleNamespace(
        id=uuid4(),
        status="completed",
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=10),
    )
    root_id = uuid4()
    child_id = uuid4()

    root_trace = _trace(
        runtime_ms=8000,
        cost=0.00047281,
        diagnostics={
            "agent_runtime_latency_ms": 8000,
            "llm_runtime_latency_ms": 7000,
            "prepare_latency_ms": 100,
            "persistence_latency_ms": 20,
            "orchestration_latency_ms": 30,
            "llm_call_count": 2,
            "input_tokens": 500,
            "output_tokens": 50,
            "total_tokens": 550,
            "usage_complete": True,
            "cost_status": "known",
            "cost_usd": 0.00047281,
            "source_count": 1,
            "fallback_used": False,
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
    )
    child_trace = _trace(
        runtime_ms=5000,
        fallback=True,
        diagnostics={
            "agent_runtime_latency_ms": 5000,
            "llm_runtime_latency_ms": 4000,
            "prepare_latency_ms": 80,
            "persistence_latency_ms": 15,
            "orchestration_latency_ms": 25,
            "llm_call_count": 1,
            "input_tokens": 300,
            "output_tokens": 60,
            "total_tokens": 360,
            "usage_complete": False,
            "cost_status": "unknown",
            "cost_usd": None,
            "source_count": 2,
            "fallback_used": True,
        },
        tools=[
            {
                "tool_name": "db_query",
                "duration_ms": 200,
                "success": False,
            }
        ],
    )

    invocations = [
        SimpleNamespace(
            id=root_id,
            trace_id=root_trace.id,
            parent_invocation_id=None,
            depth=0,
            status="completed",
        ),
        SimpleNamespace(
            id=child_id,
            trace_id=child_trace.id,
            parent_invocation_id=root_id,
            depth=1,
            status="completed",
        ),
    ]
    events = [
        _event("agent_invocation_started", root_id, started_at + timedelta(seconds=1)),
        _event("agent_invocation_started", child_id, started_at + timedelta(seconds=3)),
        _event("agent_invocation_completed", child_id, started_at + timedelta(seconds=8)),
        _event("agent_invocation_completed", root_id, started_at + timedelta(seconds=9)),
    ]

    result = build_network_run_diagnostics(
        execution=execution,
        invocations=invocations,
        events=events,
        traces_by_id={root_trace.id: root_trace, child_trace.id: child_trace},
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
    assert result["persistence_latency_ms"] == 35
    assert result["orchestration_latency_ms"] == 55
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
    invocations = [
        SimpleNamespace(
            id=root_id,
            trace_id=None,
            parent_invocation_id=None,
            depth=0,
            status="completed",
        ),
        SimpleNamespace(
            id=child_a_id,
            trace_id=None,
            parent_invocation_id=root_id,
            depth=1,
            status="completed",
        ),
        SimpleNamespace(
            id=child_b_id,
            trace_id=None,
            parent_invocation_id=root_id,
            depth=1,
            status="completed",
        ),
    ]
    events = [
        _event("agent_invocation_started", root_id, started_at),
        _event("agent_invocation_started", child_a_id, started_at + timedelta(seconds=2)),
        _event("agent_invocation_started", child_b_id, started_at + timedelta(seconds=4)),
        _event("agent_invocation_completed", child_a_id, started_at + timedelta(seconds=7)),
        _event("agent_invocation_completed", child_b_id, started_at + timedelta(seconds=9)),
        _event("agent_invocation_completed", root_id, started_at + timedelta(seconds=10)),
    ]

    result = build_network_run_diagnostics(
        execution=execution,
        invocations=invocations,
        events=events,
        traces_by_id={},
    )

    assert result["network_wall_latency_ms"] == 10000
    assert result["agent_work_latency_ms"] == 13000
    assert result["delegation_count"] == 2
    assert result["max_fan_out"] == 2
    assert result["telemetry_status"] == "partial"
