from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MarkMessageRequestInput(BaseModel):
    request_id: UUID
    status: str = Field(pattern="^(accepted|streaming|completed|failed|cancelled)$")
    target_run_id: UUID | None = None
    error_code: str | None = Field(default=None, max_length=64)


class LatestMessageRequestInput(BaseModel):
    session_binding_id: UUID


class BeginMessageRequestInput(BaseModel):
    surface_id: UUID
    session_binding_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=255)
    metadata: dict[str, Any] | None = None


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


class MessageAdmissionSurfaceState(BaseModel):
    id: UUID
    status: str
    requests_per_minute: int
    max_concurrent_runs: int


class MessageRequestRuntimeContext(BaseModel):
    request: MessageRequestState
    surface_id: UUID
    project_id: UUID
    target_type: str
    target_id: UUID
    target_release_id: UUID
    session_id: UUID


class CanonicalRunState(BaseModel):
    id: UUID
    status: str


class MessageTransitionDecision(BaseModel):
    status: str
    target_run_id: UUID | None = None
    error_code: str | None = None


class BeginMessageRequestResult(BaseModel):
    request: MessageRequestState
    created: bool
