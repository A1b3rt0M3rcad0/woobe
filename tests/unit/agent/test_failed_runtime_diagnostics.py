from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.infra.execution.instrumented_failed_finalizer import _diagnostics


def test_failed_runtime_uses_same_truthful_diagnostics_contract() -> None:
    execution = InstrumentedExecution(
        result=None,
        llm_calls=[
            {"latency_ms": 200},
            {"latency_ms": 300},
        ],
        timeline=[
            {
                "kind": "tool",
                "payload": {"provider_latency_ms": 180},
                "occurred_at": "2026-08-25T00:00:00+00:00",
            }
        ],
        tool_wall_latency_ms=250,
        tool_call_duration_sum_ms=350,
        failure_context={
            "phase": "tool_followup_1",
            "call_index": 2,
            "partial_result_available": True,
        },
    )

    diagnostics = _diagnostics(
        execution=execution,
        total_ms=1000,
        prepare_latency_ms=100,
        finalization_work_ms=50,
        usage_complete=False,
        cost_status="partial",
        cost_details={
            "cost_reason": "partial usage",
            "cost_statuses": ["known", "unknown_tokens"],
            "pricing_ids": [],
        },
        binding_payload={
            "provider_model_id": "primary-model",
            "provider_credential_id": "primary-credential",
        },
        fallback_binding_payload={
            "fallback_provider_model_id": None,
            "fallback_credential_id": None,
        },
        failure_context=execution.failure_context,
        execution_strategy="standard",
    )

    assert diagnostics["schema_version"] == 5
    assert diagnostics["execution_strategy"] == "standard"
    assert diagnostics["agent_runtime_latency_ms"] == 1000
    assert diagnostics["llm_work_latency_ms"] == 500
    assert diagnostics["tool_wall_latency_ms"] == 250
    assert diagnostics["tool_work_latency_ms"] == 350
    assert diagnostics["tool_provider_work_ms"] == 180
    assert diagnostics["tool_runtime_overhead_ms"] == 170
    assert diagnostics["finalization_work_latency_ms"] == 50
    assert diagnostics["other_latency_ms"] == 100
    assert diagnostics["orchestration_latency_ms"] is None
    assert diagnostics["failure_phase"] == "tool_followup_1"
    assert diagnostics["partial_result_available"] is True
