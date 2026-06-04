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

