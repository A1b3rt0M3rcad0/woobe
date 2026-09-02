from abc import ABC

from modules.metering.application.interfaces.repositories import (
    UsageDailyAgentRepository,
    UsageDailyProjectRepository,
    UsageEventRepository,
)


class TestUsageEventRepository:
    def test_is_abstract(self):
        assert issubclass(UsageEventRepository, ABC)

    def test_has_save_abstract(self):
        assert getattr(UsageEventRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_id_abstract(self):
        assert getattr(UsageEventRepository.get_by_id, "__isabstractmethod__", False)

    def test_has_delete_abstract(self):
        assert getattr(UsageEventRepository.delete, "__isabstractmethod__", False)


class TestUsageDailyProjectRepository:
    def test_is_abstract(self):
        assert issubclass(UsageDailyProjectRepository, ABC)

    def test_has_save_abstract(self):
        assert getattr(UsageDailyProjectRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_project_and_day_abstract(self):
        assert getattr(
            UsageDailyProjectRepository.get_by_project_and_day,
            "__isabstractmethod__",
            False,
        )


class TestUsageDailyAgentRepository:
    def test_is_abstract(self):
        assert issubclass(UsageDailyAgentRepository, ABC)

    def test_has_save_abstract(self):
        assert getattr(UsageDailyAgentRepository.save, "__isabstractmethod__", False)

    def test_has_get_by_agent_and_day_abstract(self):
        assert getattr(
            UsageDailyAgentRepository.get_by_agent_and_day,
            "__isabstractmethod__",
            False,
        )
