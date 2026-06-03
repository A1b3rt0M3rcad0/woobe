from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

import uuid6

from modules.metering.domain.enums import UsageEventType, UsageUnit


@dataclass
class UsageEvent:
    id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    agent_id: UUID | None = None
    event_type: UsageEventType = UsageEventType.llm_request
    quantity: float = 0.0
    unit: UsageUnit = UsageUnit.request
    cost_usd: float | None = None
    data: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class UsageDailyProject:
    project_id: UUID = field(default_factory=uuid6.uuid7)
    day: date | None = None
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    embedding_tokens: int = 0
    tool_calls: int = 0
    vector_queries: int = 0
    storage_mb: float = 0.0
    cost_usd: float = 0.0
    updated_at: datetime | None = None


@dataclass
class UsageDailyAgent:
    agent_id: UUID = field(default_factory=uuid6.uuid7)
    day: date | None = None
    project_id: UUID = field(default_factory=uuid6.uuid7)
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    vector_queries: int = 0
    cost_usd: float = 0.0
    updated_at: datetime | None = None
