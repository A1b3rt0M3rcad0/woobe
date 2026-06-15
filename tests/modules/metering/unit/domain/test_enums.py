from modules.metering.domain.enums import UsageEventType, UsageUnit


class TestUsageEventType:
    def test_all_values(self):
        values = {v.value for v in UsageEventType}
        assert values == {"llm_request", "embedding", "tool_call", "vector_query", "storage"}


class TestUsageUnit:
    def test_all_values(self):
        values = {v.value for v in UsageUnit}
        assert values == {"request", "token", "call", "query", "mb_second"}
