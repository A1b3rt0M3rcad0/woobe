from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

import uuid6

from modules.metering.domain.enums import UsageEventType, UsageUnit


def _uuid(value: object) -> UUID | None:
    if value in (None, ""):
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


@dataclass
class UsageEvent:
    id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    agent_id: UUID | None = None
    network_id: UUID | None = None
    network_execution_id: UUID | None = None
    network_version_id: UUID | None = None
    source_event_id: UUID | None = None
    occurred_at: datetime | None = None
    trace_id: UUID | None = None
    call_id: str | None = None
    environment: str | None = None
    agent_release_id: UUID | None = None
    agent_release_version: str | None = None
    provider: str | None = None
    model: str | None = None
    provider_model_id: UUID | None = None
    event_type: UsageEventType = UsageEventType.llm_request
    quantity: float = 0.0
    unit: UsageUnit = UsageUnit.request
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    cost_status: str | None = None
    cost_reason: str | None = None
    usage_complete: bool | None = None
    pricing_snapshot: dict | None = None
    data: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        payload = self.data or {}
        self.network_id = self.network_id or _uuid(payload.get("network_id"))
        self.network_execution_id = self.network_execution_id or _uuid(
            payload.get("network_execution_id")
        )
        self.network_version_id = self.network_version_id or _uuid(
            payload.get("network_version_id")
        )


@dataclass
class UsageDailyProject:
    project_id: UUID = field(default_factory=uuid6.uuid7)
    day: date | None = None
    requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cancelled_requests: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    embedding_tokens: int = 0
    tool_calls: int = 0
    vector_queries: int = 0
    storage_mb: float = 0.0
    cost_usd: float = 0.0
    priced_requests: int = 0
    partial_cost_requests: int = 0
    unpriced_requests: int = 0
    last_event_occurred_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class UsageDailyAgent:
    agent_id: UUID = field(default_factory=uuid6.uuid7)
    day: date | None = None
    project_id: UUID = field(default_factory=uuid6.uuid7)
    requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cancelled_requests: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    vector_queries: int = 0
    cost_usd: float = 0.0
    priced_requests: int = 0
    partial_cost_requests: int = 0
    unpriced_requests: int = 0
    last_event_occurred_at: datetime | None = None
    updated_at: datetime | None = None
