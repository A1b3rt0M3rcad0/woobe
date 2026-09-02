import inspect

from modules.observability.infra.database import (
    InboxEventModel,
    OutboxEventModel,
    TraceEventModel,
    TraceModel,
)
from modules.observability.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyTraceEventRepository,
    SQLAlchemyTraceRepository,
)


def test_observability_repository_contracts():
    models = (TraceModel, TraceEventModel, OutboxEventModel, InboxEventModel)
    assert all(model.__table__.schema == "observability" for model in models)
    assert TraceModel.__tablename__ == "traces"
    assert TraceEventModel.__tablename__ == "trace_events"
    assert OutboxEventModel.__tablename__ == "outbox_events"
    assert InboxEventModel.__tablename__ == "inbox_events"
    assert "uow" in inspect.signature(SQLAlchemyTraceRepository.__init__).parameters
    assert "uow" in inspect.signature(SQLAlchemyTraceEventRepository.__init__).parameters
    assert "uow" in inspect.signature(SQLAlchemyOutboxEventWriter.__init__).parameters
