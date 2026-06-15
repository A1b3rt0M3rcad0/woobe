from datetime import date
from uuid import UUID

from pydantic import BaseModel


class RecordUsageInput(BaseModel):
    project_id: UUID
    agent_id: UUID | None = None
    event_type: str = "llm_request"
    quantity: float = 0.0
    unit: str = "request"
    cost_usd: float | None = None
    data: dict | None = None


class RecordUsageOutput(BaseModel):
    event_id: UUID


class DailyUsageResponse(BaseModel):
    project_id: UUID | None = None
    agent_id: UUID | None = None
    day: date
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    embedding_tokens: int = 0
    tool_calls: int = 0
    vector_queries: int = 0
    storage_mb: float = 0.0
    cost_usd: float = 0.0
