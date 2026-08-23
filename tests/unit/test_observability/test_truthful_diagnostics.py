from modules.observability.infra.messaging.diagnostics_v2 import build


def test_diagnostics_use_tool_wall_time_and_keep_unknown_cost():
    diagnostics = build({
        "total_latency_ms": 5000,
        "llm_runtime_latency_ms": 3000,
        "tool_wall_latency_ms": 450,
        "tool_call_duration_sum_ms": 800,
        "tool_http_latency_ms": 700,
        "prepare_latency_ms": 100,
        "persistence_latency_ms": 50,
        "orchestration_latency_ms": 1400,
        "tool_calls": [
            {"success": True, "duration_ms": 400},
            {"success": True, "duration_ms": 400},
        ],
        "llm_calls": [{"latency_ms": 1500}, {"latency_ms": 1500}],
        "usage_complete": True,
        "cost_status": "unknown",
    })
    assert diagnostics["tool_wall_latency_ms"] == 450
    assert diagnostics["tool_call_duration_sum_ms"] == 800
    assert diagnostics["tool_call_count"] == 2
    assert diagnostics["llm_runtime_latency_ms"] == 3000
    assert diagnostics["llm_call_count"] == 2
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
    assert diagnostics["tool_call_duration_sum_ms"] == 200
    assert diagnostics["tool_call_count"] == 1
    assert diagnostics["successful_tool_calls"] == 1
    assert diagnostics["failed_tool_calls"] == 0
