from __future__ import annotations

import time
from contextvars import ContextVar
from dataclasses import dataclass

from modules.agent.application.use_cases.execution_instrumentation import (
    InstrumentedExecution,
)


@dataclass
class RequestExecutionContext:
    started_at: float
    prepare_latency_ms: int = 0
    strict_json: bool = False
    execution: InstrumentedExecution | None = None


current_execution: ContextVar[RequestExecutionContext | None] = ContextVar(
    "current_agent_execution",
    default=None,
)


def new_execution_context() -> RequestExecutionContext:
    return RequestExecutionContext(started_at=time.monotonic())
