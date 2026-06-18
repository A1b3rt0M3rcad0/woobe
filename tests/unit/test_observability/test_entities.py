from uuid import UUID

from modules.observability.domain.entities import Trace, TraceEvent
from modules.observability.domain.enums import TraceStatus, TraceEventType


class TestTrace:
    def test_defaults(self):
        trace = Trace()
        assert isinstance(trace.id, UUID)
        assert isinstance(trace.project_id, UUID)
        assert trace.agent_id is None
        assert trace.session_id is None
        assert trace.status == TraceStatus.pending
        assert trace.total_latency_ms is None
        assert trace.total_cost_usd is None
        assert trace.fallback_used is False
        assert trace.error is None
        assert trace.data is None

    def test_custom_values(self):
        trace = Trace(
            project_id=UUID("00000000-0000-0000-0000-000000000001"),
            agent_id=UUID("00000000-0000-0000-0000-000000000002"),
            session_id=UUID("00000000-0000-0000-0000-000000000003"),
            status=TraceStatus.completed,
            total_latency_ms=1250.5,
            total_cost_usd=0.05,
            provider="openai",
            model="gpt-4",
            fallback_used=True,
            data={"prompt_tokens": 500},
        )
        assert trace.status == TraceStatus.completed
        assert trace.total_latency_ms == 1250.5
        assert trace.provider == "openai"
        assert trace.fallback_used is True


class TestTraceEvent:
    def test_defaults(self):
        event = TraceEvent()
        assert isinstance(event.id, UUID)
        assert isinstance(event.trace_id, UUID)
        assert isinstance(event.project_id, UUID)
        assert event.event_type == TraceEventType.info
        assert event.latency_ms is None
        assert event.cost_usd is None
        assert event.payload is None
        assert event.payload_ref is None

    def test_custom_values(self):
        event = TraceEvent(
            trace_id=UUID("00000000-0000-0000-0000-000000000001"),
            project_id=UUID("00000000-0000-0000-0000-000000000002"),
            event_type=TraceEventType.llm_call,
            latency_ms=850.0,
            cost_usd=0.03,
            payload={"model": "gpt-4", "tokens": 150},
        )
        assert event.event_type == TraceEventType.llm_call
        assert event.latency_ms == 850.0
        assert event.cost_usd == 0.03
