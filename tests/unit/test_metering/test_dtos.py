from datetime import date
from uuid import UUID

import pytest
from pydantic import ValidationError

from modules.metering.application.dtos import (
    DailyUsageResponse,
    RecordUsageInput,
    RecordUsageOutput,
)


class TestRecordUsageInput:
    def test_valid(self):
        dto = RecordUsageInput(
            project_id=UUID("00000000-0000-0000-0000-000000000001"),
            event_type="llm_request",
            quantity=1.0,
            unit="request",
        )
        assert dto.project_id == UUID("00000000-0000-0000-0000-000000000001")
        assert dto.event_type == "llm_request"
        assert dto.quantity == 1.0

    def test_defaults(self):
        dto = RecordUsageInput(
            project_id=UUID("00000000-0000-0000-0000-000000000001"),
        )
        assert dto.agent_id is None
        assert dto.event_type == "llm_request"
        assert dto.quantity == 0.0
        assert dto.unit == "request"
        assert dto.cost_usd is None
        assert dto.data is None

    def test_missing_project_id(self):
        with pytest.raises(ValidationError):
            RecordUsageInput()


class TestRecordUsageOutput:
    def test_valid(self):
        uid = UUID("00000000-0000-0000-0000-000000000001")
        dto = RecordUsageOutput(event_id=uid)
        assert dto.event_id == uid


class TestDailyUsageResponse:
    def test_valid(self):
        d = date(2026, 6, 1)
        resp = DailyUsageResponse(
            project_id=UUID("00000000-0000-0000-0000-000000000001"),
            day=d,
            requests=100,
            input_tokens=5000,
            cost_usd=0.25,
        )
        assert resp.day == d
        assert resp.requests == 100
        assert resp.cost_usd == 0.25

    def test_defaults(self):
        resp = DailyUsageResponse(day=date(2026, 6, 1))
        assert resp.project_id is None
        assert resp.agent_id is None
        assert resp.requests == 0
