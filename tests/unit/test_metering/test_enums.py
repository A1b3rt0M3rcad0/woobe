from modules.metering.domain.enums import UsageEventType, UsageUnit


class TestUsageEventType:
    def test_members(self):
        assert UsageEventType.llm_request.value == "llm_request"
        assert UsageEventType.embedding.value == "embedding"
        assert UsageEventType.tool_call.value == "tool_call"
        assert UsageEventType.vector_query.value == "vector_query"
        assert UsageEventType.storage.value == "storage"

    def test_is_str_enum(self):
        assert issubclass(UsageEventType, str)


class TestUsageUnit:
    def test_members(self):
        assert UsageUnit.request.value == "request"
        assert UsageUnit.token.value == "token"
        assert UsageUnit.call.value == "call"
        assert UsageUnit.query.value == "query"
        assert UsageUnit.mb_second.value == "mb_second"

    def test_is_str_enum(self):
        assert issubclass(UsageUnit, str)
