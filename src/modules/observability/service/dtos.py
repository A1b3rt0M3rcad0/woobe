from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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
    event_type: str
    latency_ms: float | None = None
    cost_usd: float | None = None
    payload: dict | None = None
    payload_ref: str | None = None
    created_at: datetime | None = None


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
    created_at: datetime | None = None
    events: list[TraceEventResponse] = []


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
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime | None = None


class ListTracesInput(BaseModel):
    project_id: UUID | None = None
    agent_id: UUID | None = None
    session_id: UUID | None = None
    limit: int = 100
    offset: int = 0
