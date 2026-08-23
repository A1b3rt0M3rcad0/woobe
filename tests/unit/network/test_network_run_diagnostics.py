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


def test_network_run_diagnostics_aggregate_agent_work_without_double_counting_delegations():
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
        cost=0.01,
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
            "cost_usd": 0.01,
            "source_count": 1,
            "fallback_used": False,
        },
        tools=[
            {
                "tool_name": "delegate_to_researcher",
                "duration_ms": 3000,
                "success": True,
            },
            {
                "tool_name": "search_web",
                "duration_ms": 600,
                "success": True,
                "output": {"duration_ms": 400},
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
                "output": {"output": {"duration_ms": 150}},
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

    result = build_network_run_diagnostics(
        execution=execution,
        invocations=invocations,
        events=[],
        traces_by_id={root_trace.id: root_trace, child_trace.id: child_trace},
    )

    assert result["network_wall_latency_ms"] == 10000
    assert result["agent_work_latency_ms"] == 13000
    assert result["llm_runtime_latency_ms"] == 11000
    assert result["tool_runtime_latency_ms"] == 800
    assert result["tool_http_latency_ms"] == 550
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
    assert result["cost_usd"] == 0.01
    assert result["cost_status"] == "partial"
    assert result["fallback_count"] == 1
    assert result["source_count"] == 3
    assert result["telemetry_status"] == "complete"
