import warnings

from modules.observability.application.dtos.observability_dtos import (
    CreateTraceEventInput,
    CreateTraceEventOutput,
    CreateTraceInput,
    CreateTraceOutput,
    ListTracesInput,
    TraceEventResponse,
    TraceListItemResponse,
    TraceSummaryResponse,
)

warnings.warn(
    "Import from modules.observability.service.dtos is deprecated. "
    "Use modules.observability.application.dtos instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "CreateTraceInput",
    "CreateTraceOutput",
    "CreateTraceEventInput",
    "CreateTraceEventOutput",
    "TraceEventResponse",
    "TraceSummaryResponse",
    "TraceListItemResponse",
    "ListTracesInput",
]
