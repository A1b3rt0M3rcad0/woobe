from uuid import UUID

from modules.observability.domain.entities import Trace, TraceEvent
from modules.observability.domain.enums import TraceEventType, TraceStatus


class TestTrace:
    def test_create_with_defaults(self):
        pid = UUID("00000000-0000-0000-0000-000000000001")
        trace = Trace(project_id=pid)
        assert isinstance(trace.id, UUID)
        assert trace.project_id == pid
        assert trace.agent_id is None
        assert trace.session_id is None
        assert trace.status == TraceStatus.pending
        assert trace.started_at is None
        assert trace.ended_at is None
        assert trace.total_latency_ms is None
        assert trace.total_cost_usd is None
        assert trace.provider is None
        assert trace.model is None
        assert trace.fallback_used is False
        assert trace.error is None
        assert trace.data is None
        assert trace.created_at is None
        assert trace.updated_at is None

    def test_create_with_values(self):
        pid = UUID("00000000-0000-0000-0000-000000000001")
        aid = UUID("00000000-0000-0000-0000-000000000002")
        sid = UUID("00000000-0000-0000-0000-000000000003")
        trace = Trace(
            project_id=pid,
            agent_id=aid,
            session_id=sid,
            external_session_id="ext-session-1",
            status=TraceStatus.running,
            started_at=None,
            total_latency_ms=1500.0,
            provider="openai",
            model="gpt-4",
            fallback_used=True,
            data={"prompt_tokens": 100},
        )
        assert trace.project_id == pid
        assert trace.agent_id == aid
        assert trace.session_id == sid
        assert trace.external_session_id == "ext-session-1"
        assert trace.status == TraceStatus.running
        assert trace.total_latency_ms == 1500.0
        assert trace.provider == "openai"
        assert trace.model == "gpt-4"
        assert trace.fallback_used is True
        assert trace.data == {"prompt_tokens": 100}


class TestTraceEvent:
    def test_create_with_defaults(self):
        tid = UUID("00000000-0000-0000-0000-000000000001")
        pid = UUID("00000000-0000-0000-0000-000000000002")
        event = TraceEvent(trace_id=tid, project_id=pid)
        assert isinstance(event.id, UUID)
        assert event.trace_id == tid
        assert event.project_id == pid
        assert event.event_type == TraceEventType.info
        assert event.latency_ms is None
        assert event.cost_usd is None
        assert event.payload is None
        assert event.payload_ref is None

    def test_create_with_values(self):
        tid = UUID("00000000-0000-0000-0000-000000000001")
        pid = UUID("00000000-0000-0000-0000-000000000002")
        event = TraceEvent(
            trace_id=tid,
            project_id=pid,
            event_type=TraceEventType.llm_call,
            latency_ms=500.0,
            cost_usd=0.002,
            payload={"model": "gpt-4", "tokens": 150},
        )
        assert event.trace_id == tid
        assert event.project_id == pid
        assert event.event_type == TraceEventType.llm_call
        assert event.latency_ms == 500.0
        assert event.cost_usd == 0.002
        assert event.payload == {"model": "gpt-4", "tokens": 150}
