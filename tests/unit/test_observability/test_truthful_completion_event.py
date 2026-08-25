from modules.observability.infra.messaging.truthful_trace_projector import (
    _completion_event_payload,
)


def test_completion_event_payload_excludes_nested_execution_details() -> None:
    payload = {
        "trace_id": "trace-1",
        "project_id": "project-1",
        "agent_id": "agent-1",
        "message_id": "message-1",
        "answer_length": 2,
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
        "cost_usd": 0.001,
        "cost_status": "known",
        "usage_complete": True,
        "model": "test-model",
        "provider": "openrouter",
        "latency_ms": 500,
        "tool_calls": [{"tool_name": "sum", "output": {"result": "16"}}],
        "llm_calls": [{"phase": "tool_followup_1"}],
        "execution_events": [{"event_type": "llm.call.completed"}],
        "pricing_snapshot": {"input_cost_per_1m_tokens": 1},
        "sources": [{"document_id": "document-1"}],
    }
    diagnostics = {
        "schema_version": 4,
        "llm_call_count": 2,
        "tool_call_count": 1,
        "source_count": 1,
        "structured_output": False,
    }

    result = _completion_event_payload(payload, diagnostics)

    assert result["event"] == "agent.execution.completed.v1"
    assert result["trace_id"] == "trace-1"
    assert result["answer_length"] == 2
    assert result["llm_call_count"] == 2
    assert result["tool_call_count"] == 1
    assert result["diagnostics"] == diagnostics
    assert "tool_calls" not in result
    assert "llm_calls" not in result
    assert "execution_events" not in result
    assert "pricing_snapshot" not in result
    assert "sources" not in result
