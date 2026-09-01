from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

import uuid6

from modules.observability.domain.enums import TraceEventType, TraceStatus


@dataclass
class Trace:
    project_id: UUID
    agent_id: UUID | None = None
    session_id: UUID | None = None
    network_id: UUID | None = None
    network_execution_id: UUID | None = None
    network_session_id: UUID | None = None
    network_version_id: UUID | None = None
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
    provider_model_id: UUID | None = None
    provider_credential_id: UUID | None = None
    fallback_provider_model_id: UUID | None = None
    fallback_credential_id: UUID | None = None
    fallback_used: bool = False
    error: str | None = None
    data: dict | None = None
    id: UUID = field(default_factory=uuid6.uuid7)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class TraceEvent:
    trace_id: UUID
    project_id: UUID
    event_type: TraceEventType = TraceEventType.info
    latency_ms: float | None = None
    cost_usd: float | None = None
    payload: dict | None = None
    payload_ref: str | None = None
    id: UUID = field(default_factory=uuid6.uuid7)
    created_at: datetime | None = None
    updated_at: datetime | None = None
