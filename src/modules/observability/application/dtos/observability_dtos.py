from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


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
        """Keep the API compatible while exposing the event's owning trace.

        Existing use cases already provide the event payload. Older callers do
        not pass ``trace_id`` explicitly, so derive it from the canonical Agent
        integration-event payload rather than returning an empty value to the
        frontend.
        """
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
