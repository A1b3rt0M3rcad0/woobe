from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

import uuid6

from modules.observability.domain.enums import TraceEventType, TraceStatus


@dataclass
class Trace:
    id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    agent_id: UUID | None = None
    session_id: UUID | None = None
    external_session_id: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    status: TraceStatus = TraceStatus.pending
    started_at: datetime | None = None
    ended_at: datetime | None = None
    total_latency_ms: float | None = None
    total_cost_usd: float | None = None
    provider: str | None = None
    model: str | None = None
    fallback_used: bool = False
    error: str | None = None
    data: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class TraceEvent:
    id: UUID = field(default_factory=uuid6.uuid7)
    trace_id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    event_type: TraceEventType = TraceEventType.info
    latency_ms: float | None = None
    cost_usd: float | None = None
    payload: dict | None = None
    payload_ref: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
