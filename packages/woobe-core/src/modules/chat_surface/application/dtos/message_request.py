from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MarkMessageRequestInput(BaseModel):
    request_id: UUID
    status: str = Field(pattern="^(accepted|streaming|completed|failed|cancelled)$")
    target_run_id: UUID | None = None
    error_code: str | None = Field(default=None, max_length=64)


class MessageRequestState(BaseModel):
    id: UUID
    session_binding_id: UUID
    idempotency_key: str
    status: str
    target_run_id: UUID | None = None
    error_code: str | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
