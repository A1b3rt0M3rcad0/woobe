from modules.observability.infra.messaging.diagnostics_v2 import build


def test_diagnostics_v5_separate_wall_clock_from_cumulative_work():
    diagnostics = build({
        "agent_runtime_latency_ms": 1000,
        "llm_work_latency_ms": 500,
        "tool_wall_latency_ms": 250,
        "tool_work_latency_ms": 350,
        "prepare_latency_ms": 100,
        "finalization_work_latency_ms": 50,
        "tool_calls": [
            {"success": True, "duration_ms": 250},
            {"success": True, "duration_ms": 100},
        ],
        "llm_calls": [
            {"latency_ms": 200},
            {"latency_ms": 300},
        ],
        "usage_complete": True,
        "cost_status": "known",
    })

    assert diagnostics["schema_version"] == 5
    assert diagnostics["agent_runtime_latency_ms"] == 1000
    assert diagnostics["llm_work_latency_ms"] == 500
    assert diagnostics["tool_wall_latency_ms"] == 250
    assert diagnostics["tool_work_latency_ms"] == 350
    assert diagnostics["tool_call_duration_sum_ms"] == 350
    assert diagnostics["tool_parallelism_ratio"] == 1.4
    assert diagnostics["prepare_latency_ms"] == 100
    assert diagnostics["finalization_work_latency_ms"] == 50
    assert diagnostics["other_latency_ms"] == 100
    assert diagnostics["unaccounted_latency_ms"] == 100
    assert diagnostics["orchestration_latency_ms"] is None


def test_diagnostics_provider_work_requires_explicit_provider_latency():
    diagnostics = build({
        "total_latency_ms": 1000,
        "llm_runtime_latency_ms": 500,
        "tool_wall_latency_ms": 300,
        "tool_call_duration_sum_ms": 350,
        "prepare_latency_ms": 50,
        "persistence_latency_ms": 50,
        "tool_calls": [
            {
                "tool_name": "mcp_tool",
                "success": True,
                "duration_ms": 200,
                "output": {
                    # This used to be incorrectly interpreted as HTTP/provider latency.
                    "duration_ms": 10,
                },
            },
            {
                "tool_name": "http_tool",
                "success": True,
                "duration_ms": 150,
                "output": {
                    "provider_latency_ms": 90,
                    "duration_ms": 5,
                },
            },
        ],
    })

    assert diagnostics["tool_provider_work_ms"] == 90
    assert diagnostics["tool_runtime_overhead_ms"] == 260
    assert diagnostics["tool_http_latency_ms"] is None


def test_diagnostics_preserve_legacy_aliases_without_inventing_orchestration():
    diagnostics = build({
        "total_latency_ms": 5000,
        "llm_runtime_latency_ms": 3000,
        "tool_wall_latency_ms": 450,
        "tool_call_duration_sum_ms": 800,
        "prepare_latency_ms": 100,
        "persistence_latency_ms": 50,
        "tool_calls": [
            {"success": True, "duration_ms": 400},
            {"success": True, "duration_ms": 400},
        ],
        "llm_calls": [{"latency_ms": 1500}, {"latency_ms": 1500}],
        "usage_complete": True,
        "cost_status": "unknown",
    })

    assert diagnostics["llm_work_latency_ms"] == 3000
    assert diagnostics["llm_runtime_latency_ms"] == 3000
    assert diagnostics["tool_wall_latency_ms"] == 450
    assert diagnostics["tool_work_latency_ms"] == 800
    assert diagnostics["tool_call_duration_sum_ms"] == 800
    assert diagnostics["finalization_work_latency_ms"] == 50
    assert diagnostics["persistence_latency_ms"] == 50
    assert diagnostics["other_latency_ms"] == 1400
    assert diagnostics["orchestration_latency_ms"] is None
    assert diagnostics["cost_status"] == "unknown"


def test_diagnostics_do_not_count_internal_agent_delegation_as_tool_work():
    diagnostics = build({
        "total_latency_ms": 5000,
        "llm_runtime_latency_ms": 3000,
        "tool_wall_latency_ms": 1700,
        "tool_call_duration_sum_ms": 1700,
        "tool_calls": [
            {
                "tool_name": "delegate_to_researcher",
                "success": True,
                "duration_ms": 1500,
            },
            {
                "tool_name": "search_web",
                "success": True,
                "duration_ms": 200,
            },
        ],
        "llm_calls": [{"latency_ms": 3000}],
        "usage_complete": True,
        "cost_status": "known",
    })

    assert diagnostics["tool_wall_latency_ms"] == 200
    assert diagnostics["tool_work_latency_ms"] == 200
    assert diagnostics["tool_call_duration_sum_ms"] == 200
    assert diagnostics["tool_call_count"] == 1
    assert diagnostics["successful_tool_calls"] == 1
    assert diagnostics["failed_tool_calls"] == 0


def test_diagnostics_keep_usage_and_cost_aggregates_unchanged():
    diagnostics = build({
        "total_latency_ms": 100,
        "input_tokens": 5665,
        "output_tokens": 2411,
        "total_tokens": 8076,
        "cost_usd": 0.00146818,
        "usage_complete": True,
        "cost_status": "known",
        "llm_calls": [
            {"latency_ms": 10},
            {"latency_ms": 20},
            {"latency_ms": 30},
        ],
    })

    assert diagnostics["input_tokens"] == 5665
    assert diagnostics["output_tokens"] == 2411
    assert diagnostics["total_tokens"] == 8076
    assert diagnostics["cost_usd"] == 0.00146818
    assert diagnostics["usage_complete"] is True
    assert diagnostics["llm_call_count"] == 3
