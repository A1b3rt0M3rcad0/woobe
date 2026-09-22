from modules.agent.infra.execution.trace_event_builder import build_operation_events


def test_operation_events_include_usage_and_http_timing():
    events = build_operation_events("trace", [
        {"kind": "llm", "payload": {
            "call_id": "llm", "call_index": 1, "phase": "planning",
            "status": "success", "started_at": "2026-06-17T12:00:01+00:00",
            "ended_at": "2026-06-17T12:00:02+00:00", "latency_ms": 1000,
            "input_tokens": 100, "output_tokens": 20, "total_tokens": 120,
            "cost_usd": None, "cost_status": "unknown", "usage_complete": True,
            "provider": "custom", "model": "model",
        }},
        {"kind": "tool", "payload": {
            "tool_call_id": "tool", "tool_name": "sum_two_numbers",
            "input": {"a": 6, "b": 6}, "output": {"result": 12},
            "status": "success", "success": True,
            "started_at": "2026-06-17T12:00:02.1+00:00",
            "ended_at": "2026-06-17T12:00:02.5+00:00",
            "duration_ms": 400, "http_latency_ms": 350,
        }},
    ])
    assert [event["event_type"] for event in events] == [
        "llm.call.started", "llm.call.completed",
        "tool.call.started", "tool.call.completed",
    ]
    assert events[1]["attributes"]["total_tokens"] == 120
    assert events[1]["attributes"]["cost_status"] == "unknown"
    assert events[3]["attributes"]["http_duration_ms"] == 350
    assert events[3]["attributes"]["overhead_duration_ms"] == 50
