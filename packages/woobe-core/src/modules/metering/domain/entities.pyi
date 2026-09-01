from datetime import date, datetime
from typing import Any
from uuid import UUID


class UsageEvent:
    id: UUID
    project_id: UUID
    agent_id: UUID | None
    event_type: Any
    quantity: float
    unit: Any
    cost_usd: float | None
    data: dict[str, Any] | None
    created_at: datetime | None
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class UsageDailyProject:
    project_id: UUID
    day: date
    requests: int
    input_tokens: int
    output_tokens: int
    embedding_tokens: int
    tool_calls: int
    vector_queries: int
    storage_mb: float
    cost_usd: float
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class UsageDailyAgent:
    agent_id: UUID
    day: date
    project_id: UUID
    requests: int
    input_tokens: int
    output_tokens: int
    tool_calls: int
    vector_queries: int
    cost_usd: float
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...
