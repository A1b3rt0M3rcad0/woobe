from uuid import uuid4

from modules.metering.presentation.schemas import (
    DailyUsageResponse,
    RecordUsageRequest,
    UsageEventResponse,
)


class TestRecordUsageRequest:
    def test_valid_request(self):
        req = RecordUsageRequest(project_id=uuid4())
        assert req.event_type == "llm_request"
        assert req.quantity == 0.0


class TestUsageEventResponse:
    def test_valid_response(self):
        resp = UsageEventResponse(id=uuid4(), project_id=uuid4(), event_type="llm_request", quantity=1.0, unit="request")
        assert resp.event_type == "llm_request"
        assert resp.quantity == 1.0


class TestDailyUsageResponse:
    def test_valid_response(self):
        from datetime import date
        resp = DailyUsageResponse(project_id=uuid4(), day=date(2026, 6, 1))
        assert resp.requests == 0
        assert resp.cost_usd == 0.0
