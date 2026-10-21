from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from typing import Any

from modules.agent.domain.enums import MessageRole, RuntimeSessionMode as SessionMode, SessionStatus
from shared.contracts.content_parts import ContentPart, normalize_message_parts
from shared.contracts.artifact_output import ArtifactOutput

RuntimeEnvironment = Literal["draft", "staging", "production"]


class CreateSessionInput(BaseModel):
    project_id: UUID
    agent_id: UUID
    runtime_environment: RuntimeEnvironment = "draft"
    external_session_id: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    mode: SessionMode = SessionMode.CHAT
    data: dict | None = None


class CreateSessionOutput(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    runtime_environment: RuntimeEnvironment
    opened_release_id: UUID | None = None
    external_session_id: str | None
    tenant_id: str | None
    user_id: str | None
    status: SessionStatus
    mode: SessionMode
    data: dict | None
    external_context_snapshot: dict | None = None
    last_message_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SendMessageInput(BaseModel):
    session_id: UUID
    role: MessageRole = MessageRole.USER
    content: str = Field(default='', max_length=32_768)
    content_parts: tuple[ContentPart, ...] | None = Field(default=None, max_length=32)
    data: dict | None = None

    @model_validator(mode='after')
    def normalize_content(self):
        self.content, _ = normalize_message_parts(self.content, self.content_parts)
        return self


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
    offset: int = Field(default=0, ge=0, le=1_000_000)
    limit: int = Field(default=100, ge=1, le=1000)


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
    environment: RuntimeEnvironment | None = None
    cursor: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class ListAgentSessionsOutput(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    runtime_environment: RuntimeEnvironment
    opened_release_id: UUID | None = None
    status: SessionStatus
    mode: SessionMode
    data: dict | None = None
    external_context_snapshot: dict | None = None
    last_message_at: datetime | None = None
    created_at: datetime | None = None
    message_count: int = 0


class ListAgentSessionsPageOutput(BaseModel):
    items: list[ListAgentSessionsOutput]
    next_cursor: str | None = None
    has_next: bool = False


class AskInput(BaseModel):
    project_id: UUID
    agent_id: UUID
    message: str = Field(default='', max_length=32_768)
    content_parts: tuple[ContentPart, ...] | None = Field(default=None, max_length=32)
    resolved_content_parts: tuple[dict[str, Any], ...] = Field(default_factory=tuple, exclude=True)
    session_id: UUID | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    metadata: dict | None = None
    external_context: dict | None = None
    execution_context: str = "production"
    loaded_release_id: UUID | None = None
    snapshot_override: dict | None = None
    runtime_principal: Any = Field(default=None, exclude=True)

    @model_validator(mode='after')
    def normalize_content(self):
        self.message, _ = normalize_message_parts(self.message, self.content_parts)
        # This field is populated only after the runtime has authorized each exact
        # revision; never accept a provider-prepared projection from the caller.
        self.resolved_content_parts = ()
        return self


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
    tool_call_id: str | None = None
    tool_name: str
    input: dict | None = None
    output: dict | None = None
    duration_ms: float | None = None
    success: bool = True
    status: str | None = None
    error_code: str | None = None
    error: str | None = None


class AskOutput(BaseModel):
    runtime_identity: dict | None = None
    run_id: UUID | None = None
    status: str = "completed"
    answer: str
    suspension: dict | None = None
    session_id: UUID | None = None
    message_id: UUID | None = None
    usage: UsageInfo | None = None
    sources: list[SourceInfo] = Field(default_factory=list)
    output_artifacts: list[ArtifactOutput] = Field(default_factory=list)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[ToolCallInfo] = Field(default_factory=list)
    trace_id: UUID | None = None
    model: str | None = None
    provider: str | None = None
    provider_model_id: UUID | None = None
    provider_credential_id: UUID | None = None
    fallback_provider_model_id: UUID | None = None
    fallback_credential_id: UUID | None = None
    fallback_used: bool = False
    fallback_info: dict | None = None
    latency_ms: int | None = None
    parsed_output: dict | None = None
    output_parse_error: str | None = None
    execution_events: list[dict] = Field(default_factory=list)
    diagnostics: dict | None = None




class CreateAskJobInput(BaseModel):
    project_id: UUID
    agent_id: UUID
    message: str = Field(default='', max_length=32_768)
    content_parts: tuple[ContentPart, ...] | None = Field(default=None, max_length=32)
    session_id: UUID | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    metadata: dict | None = None
    external_context: dict | None = None
    execution_context: str = "production"

    @model_validator(mode='after')
    def normalize_content(self):
        self.message, _ = normalize_message_parts(self.message, self.content_parts)
        return self


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
