from uuid import UUID
from datetime import date, datetime

from modules.metering.domain.entities import UsageEvent, UsageDailyProject, UsageDailyAgent
from modules.metering.domain.enums import UsageEventType, UsageUnit


class TestUsageEvent:
    def test_defaults(self):
        event = UsageEvent()
        assert isinstance(event.id, UUID)
        assert isinstance(event.project_id, UUID)
        assert event.agent_id is None
        assert event.event_type == UsageEventType.llm_request
        assert event.quantity == 0.0
        assert event.unit == UsageUnit.request
        assert event.cost_usd is None
        assert event.data is None
        assert event.created_at is None
        assert event.updated_at is None

    def test_custom_values(self):
        event = UsageEvent(
            project_id=UUID("00000000-0000-0000-0000-000000000001"),
            agent_id=UUID("00000000-0000-0000-0000-000000000002"),
            event_type=UsageEventType.embedding,
            quantity=150.0,
            unit=UsageUnit.token,
            cost_usd=0.003,
            data={"model": "text-embedding-3-small"},
        )
        assert event.project_id == UUID("00000000-0000-0000-0000-000000000001")
        assert str(event.agent_id) == "00000000-0000-0000-0000-000000000002"
        assert event.event_type == UsageEventType.embedding
        assert event.quantity == 150.0
        assert event.cost_usd == 0.003
        assert event.data == {"model": "text-embedding-3-small"}


class TestUsageDailyProject:
    def test_defaults(self):
        daily = UsageDailyProject()
        assert isinstance(daily.project_id, UUID)
        assert daily.day is None
        assert daily.requests == 0
        assert daily.input_tokens == 0
        assert daily.output_tokens == 0
        assert daily.embedding_tokens == 0
        assert daily.tool_calls == 0
        assert daily.vector_queries == 0
        assert daily.storage_mb == 0.0
        assert daily.cost_usd == 0.0

    def test_custom_values(self):
        d = date(2026, 6, 1)
        daily = UsageDailyProject(
            project_id=UUID("00000000-0000-0000-0000-000000000001"),
            day=d,
            requests=100,
            input_tokens=5000,
            output_tokens=15000,
            cost_usd=0.25,
        )
        assert daily.day == d
        assert daily.requests == 100
        assert daily.input_tokens == 5000
        assert daily.cost_usd == 0.25


class TestUsageDailyAgent:
    def test_defaults(self):
        daily = UsageDailyAgent()
        assert isinstance(daily.agent_id, UUID)
        assert isinstance(daily.project_id, UUID)
        assert daily.day is None
        assert daily.requests == 0

    def test_custom_values(self):
        d = date(2026, 6, 1)
        daily = UsageDailyAgent(
            agent_id=UUID("00000000-0000-0000-0000-000000000001"),
            project_id=UUID("00000000-0000-0000-0000-000000000002"),
            day=d,
            requests=50,
            input_tokens=2500,
            cost_usd=0.12,
        )
        assert daily.requests == 50
        assert daily.cost_usd == 0.12
        assert daily.day == d
