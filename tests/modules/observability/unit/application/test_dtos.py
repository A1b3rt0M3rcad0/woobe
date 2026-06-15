from uuid import uuid4

from modules.observability.application.dtos.observability_dtos import (
    CreateTraceEventInput,
    CreateTraceInput,
    CreateTraceOutput,
    ListTracesInput,
    TraceSummaryResponse,
)


class TestCreateTraceInput:
    def test_valid_input(self):
        dto = CreateTraceInput(project_id=uuid4())
        assert dto.status == "pending"
        assert dto.fallback_used is False


class TestCreateTraceOutput:
    def test_valid_output(self):
        dto = CreateTraceOutput(trace_id=uuid4())
        assert dto.trace_id is not None


class TestCreateTraceEventInput:
    def test_valid_input(self):
        dto = CreateTraceEventInput(trace_id=uuid4(), project_id=uuid4())
        assert dto.event_type == "info"


class TestListTracesInput:
    def test_valid_input(self):
        dto = ListTracesInput()
        assert dto.limit == 100
        assert dto.offset == 0


class TestTraceSummaryResponse:
    def test_valid_response(self):
        dto = TraceSummaryResponse(id=uuid4(), project_id=uuid4(), status="pending")
        assert dto.events == []
