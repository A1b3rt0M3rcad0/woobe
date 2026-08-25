from __future__ import annotations

import time
from types import SimpleNamespace
from uuid import uuid4

from modules.agent.infra.execution.agent_run_metrics import build_agent_run_metrics


def test_agent_run_metrics_share_one_schema_across_persistence_modes() -> None:
    provider_model_id = uuid4()
    credential_id = uuid4()
    release_id = uuid4()
    execution = SimpleNamespace(
        llm_calls=[
            {
                "status": "success",
                "latency_ms": 30,
                "input_tokens": 9,
                "output_tokens": 4,
                "total_tokens": 13,
                "cost_usd": 0.002,
                "cost_status": "known",
                "cost_reason": None,
                "usage_complete": True,
                "pricing_id": "pricing-v1",
            }
        ],
        tool_calls=[SimpleNamespace(success=True)],
        timeline=[
            {
                "kind": "tool",
                "payload": {"provider_latency_ms": 6},
            }
        ],
        tool_wall_latency_ms=12,
        tool_call_duration_sum_ms=15,
    )
    context = SimpleNamespace(
        started_at=time.monotonic() - 0.1,
        execution_started_at="2026-08-25T12:00:00+00:00",
        prepare_latency_ms=5,
        execution_context="staging",
        agent_release_id=release_id,
        agent_release_version="2.0.0",
    )
    binding = SimpleNamespace(
        provider_model_id=provider_model_id,
        provider_credential_id=credential_id,
        fallback_provider_model_id=None,
        fallback_credential_id=None,
    )

    deferred = build_agent_run_metrics(
        context=context,
        execution=execution,
        binding=binding,
        fallback_used=False,
        finalization_work_ms=0,
    )
    standalone = build_agent_run_metrics(
        context=context,
        execution=execution,
        binding=binding,
        fallback_used=False,
        finalization_work_ms=12,
        usage=deferred.usage,
        usage_complete=True,
        cost_status="known",
    )

    assert deferred.usage == standalone.usage
    for field in (
        "schema_version",
        "prepare_latency_ms",
        "llm_work_latency_ms",
        "tool_wall_latency_ms",
        "tool_work_latency_ms",
        "tool_provider_work_ms",
        "tool_runtime_overhead_ms",
        "llm_call_count",
        "tool_call_count",
        "usage_complete",
        "cost_status",
        "cost_reason",
        "cost_statuses",
        "pricing_ids",
        "provider_model_id",
        "provider_credential_id",
        "fallback_provider_model_id",
        "fallback_credential_id",
        "execution_context",
        "agent_release_id",
        "agent_release_version",
        "fallback_used",
    ):
        assert deferred.diagnostics[field] == standalone.diagnostics[field]

    assert deferred.diagnostics["finalization_work_latency_ms"] == 0
    assert deferred.diagnostics["persistence_latency_ms"] == 0
    assert standalone.diagnostics["finalization_work_latency_ms"] == 12
    assert standalone.diagnostics["persistence_latency_ms"] == 12
