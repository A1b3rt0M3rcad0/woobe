from uuid import uuid4

from modules.metering.application.dtos.metering_dtos import (
    DailyUsageResponse,
    RecordUsageInput,
    RecordUsageOutput,
)


class TestRecordUsageInput:
    def test_valid_input(self):
        dto = RecordUsageInput(project_id=uuid4())
        assert dto.event_type == "llm_request"
        assert dto.unit == "request"
        assert dto.quantity == 0.0


class TestRecordUsageOutput:
    def test_valid_output(self):
        dto = RecordUsageOutput(event_id=uuid4())
        assert dto.event_id is not None


class TestDailyUsageResponse:
    def test_valid_response(self):
        from datetime import date
        dto = DailyUsageResponse(day=date(2026, 6, 1))
        assert dto.requests == 0
        assert dto.cost_usd == 0.0
