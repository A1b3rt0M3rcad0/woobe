from sqlalchemy import Index, text

from modules.observability.infra.database.models import TraceEventModel, TraceModel

TRACE_TERMINAL_OVERVIEW_INDEX = Index(
    "ix_observability_traces_project_started_terminal",
    TraceModel.project_id,
    TraceModel.started_at.desc(),
    postgresql_where=text("status IN ('completed', 'failed', 'cancelled')"),
)

TRACE_TOOL_FAILURE_OVERVIEW_INDEX = Index(
    "ix_observability_trace_events_project_created_tool",
    TraceEventModel.project_id,
    TraceEventModel.created_at.desc(),
    postgresql_where=text("event_type = 'tool_call'"),
)
