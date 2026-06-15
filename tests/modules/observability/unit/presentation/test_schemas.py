from uuid import uuid4

from modules.observability.presentation.schemas import (
    CreateTraceEventRequest,
    CreateTraceRequest,
    TraceDetailResponse,
    TraceEventResponse,
    TraceResponse,
)


class TestCreateTraceRequest:
    def test_valid_request(self):
        req = CreateTraceRequest(project_id=uuid4(), agent_id=uuid4())
        assert req.status == "pending"
        assert req.fallback_used is False


class TestCreateTraceEventRequest:
    def test_valid_request(self):
        req = CreateTraceEventRequest(project_id=uuid4())
        assert req.event_type == "info"


class TestTraceResponse:
    def test_valid_response(self):
        resp = TraceResponse(id=uuid4(), status="completed")
        assert resp.status == "completed"


class TestTraceEventResponse:
    def test_valid_response(self):
        resp = TraceEventResponse(id=uuid4(), event_type="llm_call")
        assert resp.event_type == "llm_call"


class TestTraceDetailResponse:
    def test_valid_response(self):
        trace = TraceResponse(id=uuid4(), status="completed")
        resp = TraceDetailResponse(trace=trace)
        assert resp.events == []
