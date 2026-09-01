from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTraceRequest(BaseModel):
    project_id: UUID
    agent_id: UUID
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


class CreateTraceEventRequest(BaseModel):
    project_id: UUID
    event_type: str = "info"
    latency_ms: float | None = None
    cost_usd: float | None = None
    payload: dict | None = None
    payload_ref: str | None = None


class TraceResponse(BaseModel):
    id: UUID
    status: str
    provider: str | None = None
    model: str | None = None
    total_latency_ms: float | None = None
    total_cost_usd: float | None = None
    error: str | None = None
    data: dict | None = None
    created_at: datetime | None = None


class TraceEventResponse(BaseModel):
    id: UUID
    event_type: str
    latency_ms: float | None = None
    cost_usd: float | None = None
    payload: dict | None = None
    created_at: datetime | None = None


class TraceDetailResponse(BaseModel):
    trace: TraceResponse
    events: list[TraceEventResponse] = []
