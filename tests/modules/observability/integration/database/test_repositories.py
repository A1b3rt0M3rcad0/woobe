import inspect

from modules.observability.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyTraceEventRepository,
    SQLAlchemyTraceRepository,
)
from modules.observability.infra.database import (
    InboxEventModel,
    OutboxEventModel,
    TraceEventModel,
    TraceModel,
)


class TestObservabilityRepositoriesImports:
    def test_trace_repository_importable(self):
        assert SQLAlchemyTraceRepository is not None

    def test_trace_event_repository_importable(self):
        assert SQLAlchemyTraceEventRepository is not None

    def test_outbox_writer_importable(self):
        assert SQLAlchemyOutboxEventWriter is not None

    def test_models_importable(self):
        assert TraceModel is not None
        assert TraceEventModel is not None
        assert OutboxEventModel is not None
        assert InboxEventModel is not None

    def test_models_have_correct_schema(self):
        assert TraceModel.__table_args__["schema"] == "observability"
        assert TraceEventModel.__table_args__["schema"] == "observability"
        assert OutboxEventModel.__table_args__["schema"] == "observability"
        assert InboxEventModel.__table_args__["schema"] == "observability"

    def test_models_have_correct_tablename(self):
        assert TraceModel.__tablename__ == "traces"
        assert TraceEventModel.__tablename__ == "trace_events"
        assert OutboxEventModel.__tablename__ == "outbox_events"
        assert InboxEventModel.__tablename__ == "inbox_events"

    def test_trace_repository_accepts_session(self):
        sig = inspect.signature(SQLAlchemyTraceRepository.__init__)
        assert "session" in sig.parameters

    def test_trace_event_repository_accepts_session(self):
        sig = inspect.signature(SQLAlchemyTraceEventRepository.__init__)
        assert "session" in sig.parameters
