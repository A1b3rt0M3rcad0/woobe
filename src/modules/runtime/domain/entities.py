from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from modules.runtime.domain.enums import MessageRole, SessionMode, SessionStatus


@dataclass
class Session:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID | None = None
    agent_id: UUID | None = None
    external_session_id: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    status: SessionStatus = SessionStatus.ACTIVE
    mode: SessionMode = SessionMode.CHAT
    data: dict | None = None
    last_message_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Message:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID | None = None
    agent_id: UUID | None = None
    session_id: UUID | None = None
    role: MessageRole = MessageRole.USER
    content: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    data: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

