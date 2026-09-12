from uuid import uuid4

import pytest

from modules.observability.domain.entities import Trace
from modules.observability.infra.messaging import truthful_trace_projector as projector
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


@pytest.mark.asyncio
async def test_journal_completion_projects_known_cost_from_nested_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace_id = uuid4()
    project_id = uuid4()
    agent_id = uuid4()
    trace = Trace(id=trace_id, project_id=project_id, agent_id=agent_id, data={})

    class FakeTraceRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_id(self, requested_trace_id):
            assert requested_trace_id == trace_id
            return trace

        async def save(self, candidate: Trace) -> None:
            assert candidate is trace

    class FakeTraceEventRepository:
        def __init__(self, _session: object) -> None:
            pass

    async def fake_legacy_project(**_kwargs) -> None:
        return None

    async def fake_save_event(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(projector, "SQLAlchemyTraceRepository", FakeTraceRepository)
    monkeypatch.setattr(
        projector,
        "SQLAlchemyTraceEventRepository",
        FakeTraceEventRepository,
    )
    monkeypatch.setattr(projector, "legacy_project", fake_legacy_project)
    monkeypatch.setattr(projector, "_save_event", fake_save_event)

    await projector.project_agent_event(
        event_type="agent.execution.completed.v1",
        payload={
            "trace_id": str(trace_id),
            "project_id": str(project_id),
            "agent_id": str(agent_id),
            "cost_usd": 0.001178,
            "usage": {"cost_usd": 0.001178},
            "diagnostics": {
                "schema_version": 5,
                "cost_status": "known",
                "usage_complete": True,
            },
            "total_latency_ms": 1250,
        },
        session=object(),
    )

    assert trace.total_cost_usd == pytest.approx(0.001178)
    assert trace.data is not None
    assert trace.data["cost_status"] == "known"
