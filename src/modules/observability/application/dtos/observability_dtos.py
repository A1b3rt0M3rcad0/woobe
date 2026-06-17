from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


_TRACE_EVENT_ORDER = {
    "agent.execution.requested.v1": 10,
    "agent.execution.started.v1": 20,
    "agent.execution.llm_completed.v1": 30,
    "agent.execution.tool_completed.v1": 40,
    "agent.execution.fallback_triggered.v1": 50,
    "agent.execution.completed.v1": 90,
    "agent.execution.failed.v1": 90,
}


def _trace_event_sort_key(event: "TraceEventResponse") -> tuple[int, float, str]:
    payload = event.payload if isinstance(event.payload, dict) else {}
    integration_event = payload.get("event")
    lifecycle_order = _TRACE_EVENT_ORDER.get(str(integration_event), 60)
    created_at = event.created_at.timestamp() if event.created_at is not None else float("-inf")
    return lifecycle_order, created_at, str(event.id)


class CreateTraceInput(BaseModel):
    project_id: UUID
    agent_id: UUID | None = None
    session_id: UUID | None = None
    external_session_id: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    status: str = "pending"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    total_latency_ms: float | None = None
    total_cost_usd: float | None = None
    provider: str | None = None
    model: str | None = None
    fallback_used: bool = False
    error: str | None = None
    data: dict | None = None


class CreateTraceOutput(BaseModel):
    trace_id: UUID


class CreateTraceEventInput(BaseModel):
    trace_id: UUID
    project_id: UUID
    event_type: str = "info"
    latency_ms: float | None = None
    cost_usd: float | None = None
    payload: dict | None = None
    payload_ref: str | None = None


class CreateTraceEventOutput(BaseModel):
    event_id: UUID


class TraceEventResponse(BaseModel):
    id: UUID
    trace_id: UUID | None = None
    event_type: str
    latency_ms: float | None = None
    cost_usd: float | None = None
    payload: dict | None = None
    payload_ref: str | None = None
    created_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def derive_trace_id_from_payload(cls, value: Any) -> Any:
        if not isinstance(value, dict) or value.get("trace_id"):
            return value
        payload = value.get("payload")
        if not isinstance(payload, dict):
            return value
        raw_trace_id = payload.get("trace_id") or payload.get("execution_id")
        if raw_trace_id is None:
            return value
        normalized = dict(value)
        normalized["trace_id"] = raw_trace_id
        return normalized


class TraceSummaryResponse(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID | None = None
    session_id: UUID | None = None
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    total_latency_ms: float | None = None
    total_cost_usd: float | None = None
    provider: str | None = None
    model: str | None = None
    error: str | None = None
    data: dict | None = None
    created_at: datetime | None = None
    events: list[TraceEventResponse] = Field(default_factory=list)

    @model_validator(mode="after")
    def order_events_by_execution_lifecycle(self) -> "TraceSummaryResponse":
        self.events = sorted(self.events, key=_trace_event_sort_key)
        return self


class TraceListItemResponse(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID | None = None
    session_id: UUID | None = None
    status: str
    provider: str | None = None
    model: str | None = None
    total_latency_ms: float | None = None
    total_cost_usd: float | None = None
    error: str | None = None
    data: dict | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime | None = None


class ListTracesInput(BaseModel):
    project_id: UUID | None = None
    agent_id: UUID | None = None
    session_id: UUID | None = None
    limit: int = 100
    offset: int = 0
