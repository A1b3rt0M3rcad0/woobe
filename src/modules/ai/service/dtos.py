from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from modules.ai.domain.enums import (
    AgentStatus,
    AgentType,
    CredentialStatus,
    Provider,
    SessionMode,
)


class CreateProviderCredentialInput(BaseModel):
    project_id: UUID
    provider: Provider
    name: str
    secret: str
    metadata: dict[str, Any] = {}


class CreateProviderCredentialOutput(BaseModel):
    id: UUID
    project_id: UUID
    provider: Provider
    name: str
    status: CredentialStatus
    created_at: datetime | None = None
    metadata: dict[str, Any] = {}


class CreateAgentInput(BaseModel):
    project_id: UUID
    provider_credential_id: UUID | None = None
    fallback_credential_id: UUID | None = None
    name: str
    description: str = ""
    type: AgentType = AgentType.chat
    system_prompt: str = ""
    provider: Provider = Provider.openai
    model: str
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode = SessionMode.stateless
    settings: dict[str, Any] = {}


class CreateAgentOutput(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    type: AgentType
    provider: Provider
    model: str
    status: AgentStatus
    created_at: datetime | None = None


class UpdateAgentInput(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    provider: Provider | None = None
    model: str | None = None
    provider_credential_id: UUID | None = None
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    fallback_credential_id: UUID | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode | None = None
    status: AgentStatus | None = None
    settings: dict[str, Any] | None = None


class UpdateAgentOutput(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    type: AgentType
    provider: Provider
    model: str
    provider_credential_id: UUID | None = None
    fallback_credential_id: UUID | None = None
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode
    system_prompt: str
    description: str
    status: AgentStatus
    settings: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None
