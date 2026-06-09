from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from modules.runtime.domain.enums import MessageRole, SessionMode, SessionStatus


class CreateSessionInput(BaseModel):
    project_id: UUID
    agent_id: UUID
    external_session_id: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    mode: SessionMode = SessionMode.CHAT
    data: dict | None = None


class CreateSessionOutput(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    external_session_id: str | None
    tenant_id: str | None
    user_id: str | None
    status: SessionStatus
    mode: SessionMode
    data: dict | None
    last_message_at: datetime | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SendMessageInput(BaseModel):
    session_id: UUID
    role: MessageRole = MessageRole.USER
    content: str = Field(..., min_length=1)
    data: dict | None = None


class MessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    data: dict | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SendMessageOutput(BaseModel):
    message: MessageResponse
    session_id: UUID


class ListMessagesInput(BaseModel):
    session_id: UUID
    offset: int = 0
    limit: int = 100


class ListMessagesOutput(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    data: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ListAgentSessionsInput(BaseModel):
    project_id: UUID
    agent_id: UUID


class ListAgentSessionsOutput(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    status: SessionStatus
    mode: SessionMode
    last_message_at: datetime | None = None
    created_at: datetime | None = None
    message_count: int = 0


class AskInput(BaseModel):
    project_id: UUID
    agent_id: UUID
    message: str = Field(..., min_length=1)
    session_id: UUID | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    metadata: dict | None = None


class UsageInfo(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None


class SourceInfo(BaseModel):
    document_id: str | None = None
    document_title: str | None = None
    chunk_id: str | None = None
    page_number: int | None = None
    score: float | None = None
    content_preview: str | None = None


class ToolCallInfo(BaseModel):
    tool_name: str
    input: dict | None = None
    output: dict | None = None
    duration_ms: float | None = None


class AskOutput(BaseModel):
    answer: str
    session_id: UUID | None = None
    message_id: UUID | None = None
    usage: UsageInfo | None = None
    sources: list[SourceInfo] = []
    tool_calls: list[ToolCallInfo] = []
    trace_id: UUID | None = None
    model: str | None = None
    provider: str | None = None
    fallback_used: bool = False
    latency_ms: int | None = None
    parsed_output: dict | None = None
    output_parse_error: str | None = None


class CreateAskJobInput(BaseModel):
    project_id: UUID
    agent_id: UUID
    message: str = Field(..., min_length=1)
    session_id: UUID | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    metadata: dict | None = None


class CreateAskJobOutput(BaseModel):
    job_id: UUID
    status: str = "pending"


class GetAskJobOutput(BaseModel):
    job_id: UUID
    status: str
    result: dict | None = None
    error: str | None = None
    trace_id: UUID | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
