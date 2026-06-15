from modules.observability.domain.enums import TraceEventType, TraceStatus


class TestTraceStatus:
    def test_all_values(self):
        values = {v.value for v in TraceStatus}
        assert values == {"pending", "running", "completed", "failed", "cancelled"}


class TestTraceEventType:
    def test_all_values(self):
        values = {v.value for v in TraceEventType}
        assert values == {"llm_call", "tool_call", "vector_query", "error", "warning", "info"}
