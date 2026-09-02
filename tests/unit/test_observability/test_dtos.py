from uuid import UUID
from datetime import datetime

from pydantic import ValidationError
import pytest

from modules.observability.application.dtos import (
    CreateTraceInput,
    CreateTraceOutput,
    CreateTraceEventInput,
    CreateTraceEventOutput,
    TraceEventResponse,
    TraceSummaryResponse,
)


class TestCreateTraceInput:
    def test_valid(self):
        dto = CreateTraceInput(
            project_id=UUID("00000000-0000-0000-0000-000000000001"),
        )
        assert dto.status == "pending"
        assert dto.fallback_used is False
        assert dto.agent_id is None

    def test_missing_project_id(self):
        with pytest.raises(ValidationError):
            CreateTraceInput()

    def test_all_fields(self):
        dto = CreateTraceInput(
            project_id=UUID("00000000-0000-0000-0000-000000000001"),
            agent_id=UUID("00000000-0000-0000-0000-000000000002"),
            status="running",
            provider="openai",
            model="gpt-4",
            fallback_used=True,
        )
        assert dto.status == "running"
        assert dto.provider == "openai"
        assert dto.fallback_used is True


class TestCreateTraceOutput:
    def test_valid(self):
        uid = UUID("00000000-0000-0000-0000-000000000001")
        dto = CreateTraceOutput(trace_id=uid)
        assert dto.trace_id == uid


class TestCreateTraceEventInput:
    def test_valid(self):
        dto = CreateTraceEventInput(
            trace_id=UUID("00000000-0000-0000-0000-000000000001"),
            project_id=UUID("00000000-0000-0000-0000-000000000002"),
        )
        assert dto.event_type == "info"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            CreateTraceEventInput()


class TestCreateTraceEventOutput:
    def test_valid(self):
        uid = UUID("00000000-0000-0000-0000-000000000001")
        dto = CreateTraceEventOutput(event_id=uid)
        assert dto.event_id == uid


class TestTraceEventResponse:
    def test_valid(self):
        now = datetime.now()
        resp = TraceEventResponse(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            event_type="llm_call",
            latency_ms=500.0,
            cost_usd=0.02,
            created_at=now,
        )
        assert resp.event_type == "llm_call"
        assert resp.latency_ms == 500.0
        assert resp.created_at == now


class TestTraceSummaryResponse:
    def test_valid(self):
        now = datetime.now()
        resp = TraceSummaryResponse(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            project_id=UUID("00000000-0000-0000-0000-000000000002"),
            status="completed",
            total_latency_ms=1500.0,
            provider="openai",
            created_at=now,
        )
        assert resp.status == "completed"
        assert resp.events == []

    def test_with_events(self):
        event = TraceEventResponse(
            id=UUID("00000000-0000-0000-0000-000000000010"),
            event_type="llm_call",
        )
        resp = TraceSummaryResponse(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            project_id=UUID("00000000-0000-0000-0000-000000000002"),
            status="completed",
            events=[event],
        )
        assert len(resp.events) == 1
        assert resp.events[0].event_type == "llm_call"
