from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class RecordUsageRequest(BaseModel):
    project_id: UUID
    agent_id: UUID | None = None
    event_type: str = "llm_request"
    quantity: float = 0.0
    unit: str = "request"
    cost_usd: float | None = None
    data: dict | None = None


class UsageEventResponse(BaseModel):
    id: UUID
    project_id: UUID
    event_type: str
    quantity: float
    unit: str
    cost_usd: float | None = None
    created_at: datetime | None = None


class DailyUsageResponse(BaseModel):
    project_id: UUID
    day: date
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
