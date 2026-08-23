from __future__ import annotations

import time
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from modules.agent.application.interfaces.execution import InstrumentedExecution


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RequestExecutionContext:
    started_at: float
    request_received_at: str
    execution_started_at: str
    client_sent_at: str | None = None
    project_id: UUID | None = None
    agent_id: UUID | None = None
    session_id: UUID | None = None
    trace_id: UUID | None = None
    prepare_started_at: str | None = None
    prepare_ended_at: str | None = None
    prepare_latency_ms: int = 0
    strict_json: bool = False
    execution: InstrumentedExecution | None = None
    execution_context: str | None = None
    agent_release_id: UUID | None = None
    agent_release_version: str | None = None
    rag_metadata: dict[str, Any] | None = None
    tool_snapshots: dict[str, dict[str, Any]] | None = None
    tool_metadata: dict[str, Any] | None = None
    persisted_sources: list[Any] | None = None
    network_id: UUID | None = None
    network_version_id: UUID | None = None
    network_session_id: UUID | None = None
    network_execution_id: UUID | None = None
    network_invocation_id: UUID | None = None
    parent_invocation_id: UUID | None = None
    network_node_id: UUID | None = None
    depth: int | None = None
    internal_tool_definitions: list[dict[str, Any]] | None = None
    internal_tool_name_to_id: dict[str, str] | None = None


current_execution: ContextVar[RequestExecutionContext | None] = ContextVar(
    "current_agent_execution",
    default=None,
)


def new_execution_context(
    request_received_at: str | None = None,
    client_sent_at: str | None = None,
) -> RequestExecutionContext:
    now = utc_now()
    return RequestExecutionContext(
        started_at=time.monotonic(),
        request_received_at=request_received_at or now,
        execution_started_at=now,
        client_sent_at=client_sent_at,
    )
