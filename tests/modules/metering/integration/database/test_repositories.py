import inspect

from modules.metering.infra.database.repositories import (
    SQLAlchemyUsageDailyAgentRepository,
    SQLAlchemyUsageDailyProjectRepository,
    SQLAlchemyUsageEventRepository,
)
from modules.metering.infra.database import (
    UsageDailyAgentModel,
    UsageDailyProjectModel,
    UsageEventModel,
)


class TestMeteringRepositoriesImports:
    def test_event_repository_importable(self):
        assert SQLAlchemyUsageEventRepository is not None

    def test_daily_project_repository_importable(self):
        assert SQLAlchemyUsageDailyProjectRepository is not None

    def test_daily_agent_repository_importable(self):
        assert SQLAlchemyUsageDailyAgentRepository is not None

    def test_models_importable(self):
        assert UsageEventModel is not None
        assert UsageDailyProjectModel is not None
        assert UsageDailyAgentModel is not None

    def test_models_have_correct_schema(self):
        assert UsageEventModel.__table_args__["schema"] == "metering"
        assert UsageDailyProjectModel.__table_args__["schema"] == "metering"
        assert UsageDailyAgentModel.__table_args__["schema"] == "metering"

    def test_models_have_correct_tablename(self):
        assert UsageEventModel.__tablename__ == "usage_events"
        assert UsageDailyProjectModel.__tablename__ == "usage_daily_project"
        assert UsageDailyAgentModel.__tablename__ == "usage_daily_agent"

    def test_event_repository_accepts_session(self):
        sig = inspect.signature(SQLAlchemyUsageEventRepository)
        assert "session" in sig.parameters

    def test_daily_project_repository_accepts_session(self):
        sig = inspect.signature(SQLAlchemyUsageDailyProjectRepository)
        assert "session" in sig.parameters

    def test_daily_agent_repository_accepts_session(self):
        sig = inspect.signature(SQLAlchemyUsageDailyAgentRepository)
        assert "session" in sig.parameters
