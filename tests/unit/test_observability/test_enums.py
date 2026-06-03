from modules.observability.domain.enums import TraceStatus, TraceEventType


class TestTraceStatus:
    def test_members(self):
        assert TraceStatus.pending.value == "pending"
        assert TraceStatus.running.value == "running"
        assert TraceStatus.completed.value == "completed"
        assert TraceStatus.failed.value == "failed"
        assert TraceStatus.cancelled.value == "cancelled"

    def test_is_str_enum(self):
        assert issubclass(TraceStatus, str)


class TestTraceEventType:
    def test_members(self):
        assert TraceEventType.llm_call.value == "llm_call"
        assert TraceEventType.tool_call.value == "tool_call"
        assert TraceEventType.vector_query.value == "vector_query"
        assert TraceEventType.error.value == "error"
        assert TraceEventType.warning.value == "warning"
        assert TraceEventType.info.value == "info"

    def test_is_str_enum(self):
        assert issubclass(TraceEventType, str)
