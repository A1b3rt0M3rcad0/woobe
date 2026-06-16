from uuid import UUID

from modules.metering.domain.entities import UsageDailyAgent, UsageDailyProject, UsageEvent
from modules.metering.domain.enums import UsageEventType, UsageUnit


class TestUsageEvent:
    def test_create_with_defaults(self):
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

    def test_create_with_values(self):
        pid = UUID("00000000-0000-0000-0000-000000000001")
        aid = UUID("00000000-0000-0000-0000-000000000002")
        event = UsageEvent(
            project_id=pid,
            agent_id=aid,
            event_type=UsageEventType.embedding,
            quantity=150.0,
            unit=UsageUnit.token,
            cost_usd=0.003,
            data={"model": "text-embedding-3-small"},
        )
        assert event.project_id == pid
        assert event.agent_id == aid
        assert event.event_type == UsageEventType.embedding
        assert event.quantity == 150.0
        assert event.unit == UsageUnit.token
        assert event.cost_usd == 0.003
        assert event.data == {"model": "text-embedding-3-small"}


class TestUsageDailyProject:
    def test_create_with_defaults(self):
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
        assert daily.updated_at is None

    def test_create_with_values(self):
        from datetime import date

        pid = UUID("00000000-0000-0000-0000-000000000001")
        daily = UsageDailyProject(
            project_id=pid,
            day=date(2026, 6, 1),
            requests=100,
            input_tokens=5000,
            output_tokens=15000,
            embedding_tokens=2000,
            tool_calls=10,
            vector_queries=25,
            storage_mb=1.5,
            cost_usd=0.05,
        )
        assert daily.project_id == pid
        assert daily.day == date(2026, 6, 1)
        assert daily.cost_usd == 0.05


class TestUsageDailyAgent:
    def test_create_with_defaults(self):
        daily = UsageDailyAgent()
        assert isinstance(daily.agent_id, UUID)
        assert isinstance(daily.project_id, UUID)
        assert daily.day is None
        assert daily.requests == 0
        assert daily.cost_usd == 0.0

    def test_create_with_values(self):
        from datetime import date

        aid = UUID("00000000-0000-0000-0000-000000000001")
        pid = UUID("00000000-0000-0000-0000-000000000002")
        daily = UsageDailyAgent(
            agent_id=aid,
            day=date(2026, 6, 1),
            project_id=pid,
            requests=50,
            input_tokens=2000,
            output_tokens=8000,
            tool_calls=5,
            vector_queries=10,
            cost_usd=0.02,
        )
        assert daily.agent_id == aid
        assert daily.project_id == pid
        assert daily.requests == 50
        assert daily.cost_usd == 0.02
