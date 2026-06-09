from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from modules.runtime.domain.enums import MessageRole, SessionMode, SessionStatus


class CreateSessionRequest(BaseModel):
    project_id: UUID
    agent_id: UUID
    external_session_id: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    mode: SessionMode = SessionMode.CHAT
    data: dict | None = None


class SessionResponse(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    external_session_id: str | None
    tenant_id: str | None
    user_id: str | None
    status: SessionStatus
    mode: SessionMode
    data: dict | None
    last_message_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SendMessageRequest(BaseModel):
    session_id: UUID
    content: str = Field(..., min_length=1)
    data: dict | None = None


class MessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    data: dict | None = None
    created_at: datetime
    updated_at: datetime


class AskRequest(BaseModel):
    project_id: UUID
    agent_id: UUID
    message: str = Field(..., min_length=1)
    session_id: UUID | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    metadata: dict | None = None
    execution_context: str = "playground"
    loaded_release_id: UUID | None = None
    snapshot_override: dict | None = None


class UsageResponse(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None


class SourceResponse(BaseModel):
    document_id: str | None = None
    document_title: str | None = None
    chunk_id: str | None = None
    page_number: int | None = None
    score: float | None = None
    content_preview: str | None = None


class ToolCallResponse(BaseModel):
    tool_name: str
    input: dict | None = None
    output: dict | None = None
    duration_ms: float | None = None


class AskResponse(BaseModel):
    answer: str
    session_id: UUID | None = None
    message_id: UUID | None = None
    usage: UsageResponse | None = None
    sources: list[SourceResponse] = []
    tool_calls: list[ToolCallResponse] = []
    trace_id: UUID | None = None
    model: str | None = None
    provider: str | None = None
    fallback_used: bool = False
    latency_ms: int | None = None
    parsed_output: dict | None = None
    output_parse_error: str | None = None
