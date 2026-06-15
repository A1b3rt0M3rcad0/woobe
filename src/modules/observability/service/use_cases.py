import warnings

from modules.observability.application.use_cases.observability_use_cases import (
    CreateTraceEventUseCase,
    CreateTraceUseCase,
    GetTraceUseCase,
    ListTracesUseCase,
)

warnings.warn(
    "Import from modules.observability.service.use_cases is deprecated. "
    "Use modules.observability.application.use_cases instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "CreateTraceUseCase",
    "CreateTraceEventUseCase",
    "GetTraceUseCase",
    "ListTracesUseCase",
]
