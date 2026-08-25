from __future__ import annotations

import time
from types import SimpleNamespace
from uuid import uuid4

from modules.agent.infra.execution.deferred_run_metrics import build_deferred_agent_metrics


def test_deferred_agent_metrics_match_agent_run_v5_contract() -> None:
    provider_model_id = uuid4()
    credential_id = uuid4()
    release_id = uuid4()
    execution = SimpleNamespace(
        llm_calls=[
            {
                "status": "success",
                "latency_ms": 24,
                "input_tokens": 11,
                "output_tokens": 7,
                "total_tokens": 18,
                "cost_usd": 0.003,
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
                "payload": {"provider_latency_ms": 5},
            }
        ],
        tool_wall_latency_ms=8,
        tool_call_duration_sum_ms=10,
    )
    context = SimpleNamespace(
        execution=execution,
        started_at=time.monotonic() - 0.05,
        execution_started_at="2026-08-25T12:00:00+00:00",
        prepare_latency_ms=3,
        execution_context="staging",
        agent_release_id=release_id,
        agent_release_version="1.2.3",
    )
    output = SimpleNamespace(
        answer="done",
        tool_calls=[SimpleNamespace(success=True)],
        sources=[SimpleNamespace()],
        provider_model_id=provider_model_id,
        provider_credential_id=credential_id,
        fallback_provider_model_id=None,
        fallback_credential_id=None,
        fallback_used=False,
    )

    metrics = build_deferred_agent_metrics(context, output)

    assert metrics.usage == {
        "input_tokens": 11,
        "output_tokens": 7,
        "total_tokens": 18,
        "cost_usd": 0.003,
    }
    assert metrics.diagnostics["schema_version"] == 5
    assert metrics.diagnostics["llm_work_latency_ms"] == 24
    assert metrics.diagnostics["tool_wall_latency_ms"] == 8
    assert metrics.diagnostics["tool_work_latency_ms"] == 10
    assert metrics.diagnostics["tool_provider_work_ms"] == 5
    assert metrics.diagnostics["tool_runtime_overhead_ms"] == 5
    assert metrics.diagnostics["finalization_work_latency_ms"] == 0
    assert metrics.diagnostics["persistence_latency_ms"] == 0
    assert metrics.diagnostics["usage_complete"] is True
    assert metrics.diagnostics["cost_status"] == "known"
    assert metrics.diagnostics["cost_usd"] == 0.003
    assert metrics.diagnostics["pricing_ids"] == ["pricing-v1"]
    assert metrics.diagnostics["provider_model_id"] == str(provider_model_id)
    assert metrics.diagnostics["provider_credential_id"] == str(credential_id)
    assert metrics.diagnostics["agent_release_id"] == str(release_id)
    assert metrics.diagnostics["agent_release_version"] == "1.2.3"
    assert metrics.diagnostics["source_count"] == 1
    assert metrics.diagnostics["answer_length"] == 4
    assert metrics.started_at == context.execution_started_at
    assert metrics.completed_at >= metrics.started_at
