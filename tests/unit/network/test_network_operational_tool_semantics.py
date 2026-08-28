from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from modules.network.infra.database.run_diagnostics_reader import (
    build_network_run_diagnostics,
)


def _run(*, run_id, parent_run_id, started_at, completed_at, tool_calls, tool_work_latency_ms):
    return SimpleNamespace(
        id=run_id,
        agent_id=uuid4(),
        parent_run_id=parent_run_id,
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
        usage={
            "input_tokens": 1,
            "output_tokens": 1,
            "total_tokens": 2,
            "cost_usd": 0,
        },
        result={
            "diagnostics": {
                "schema_version": 5,
                "llm_work_latency_ms": 1,
                "tool_work_latency_ms": tool_work_latency_ms,
                "prepare_latency_ms": 0,
                "finalization_work_latency_ms": 0,
                "llm_call_count": 1,
                "usage_complete": True,
                "cost_status": "known",
                "cost_usd": 0,
            },
            "tool_calls": tool_calls,
            "sources": [],
            "llm_calls": [{}],
            "cost_status": "known",
            "cost_usd": 0,
        },
    )


def _invocation(invocation_id, parent_id, depth):
    return SimpleNamespace(
        id=invocation_id,
        parent_invocation_id=parent_id,
        depth=depth,
    )


def _execution(started_at, completed_at):
    return SimpleNamespace(
        id=uuid4(),
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
    )


def test_delegation_only_network_has_zero_operational_tool_work() -> None:
    started = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
    root_id = uuid4()
    child_id = uuid4()
    root = _run(
        run_id=root_id,
        parent_run_id=None,
        started_at=started,
        completed_at=started + timedelta(seconds=30),
        tool_calls=[
            {
                "tool_name": "delegate_to_support",
                "duration_ms": 27_700,
                "success": True,
            }
        ],
        tool_work_latency_ms=27_700,
    )
    child = _run(
        run_id=child_id,
        parent_run_id=root_id,
        started_at=started + timedelta(seconds=1),
        completed_at=started + timedelta(seconds=28),
        tool_calls=[],
        tool_work_latency_ms=0,
    )

    result = build_network_run_diagnostics(
        execution=_execution(started, started + timedelta(seconds=30)),
        invocations=[
            _invocation(root_id, None, 0),
            _invocation(child_id, root_id, 1),
        ],
        agent_runs=[root, child],
    )

    assert result["delegation_count"] == 1
    assert result["tool_call_count"] == 0
    assert result["tool_work_latency_ms"] == 0


def test_network_tool_work_counts_only_external_tool_duration() -> None:
    started = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
    root_id = uuid4()
    child_id = uuid4()
    root = _run(
        run_id=root_id,
        parent_run_id=None,
        started_at=started,
        completed_at=started + timedelta(seconds=25),
        tool_calls=[
            {
                "tool_name": "delegate_to_support",
                "duration_ms": 20_000,
                "success": True,
            },
            {
                "tool_name": "lookup_customer",
                "duration_ms": 120,
                "success": True,
            },
        ],
        tool_work_latency_ms=20_120,
    )
    child = _run(
        run_id=child_id,
        parent_run_id=root_id,
        started_at=started + timedelta(seconds=1),
        completed_at=started + timedelta(seconds=21),
        tool_calls=[],
        tool_work_latency_ms=0,
    )

    result = build_network_run_diagnostics(
        execution=_execution(started, started + timedelta(seconds=25)),
        invocations=[
            _invocation(root_id, None, 0),
            _invocation(child_id, root_id, 1),
        ],
        agent_runs=[root, child],
    )

    assert result["delegation_count"] == 1
    assert result["tool_call_count"] == 1
    assert result["successful_tool_calls"] == 1
    assert result["tool_work_latency_ms"] == 120
