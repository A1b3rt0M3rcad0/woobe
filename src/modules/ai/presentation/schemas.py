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


class CreateProviderCredentialRequest(BaseModel):
    project_id: UUID
    provider: Provider
    name: str
    secret: str
    metadata: dict[str, Any] = {}


class ProviderCredentialResponse(BaseModel):
    id: UUID
    project_id: UUID
    provider: Provider
    name: str
    status: CredentialStatus
    created_at: datetime | None = None
    metadata: dict[str, Any] = {}


class CreateAgentRequest(BaseModel):
    project_id: UUID
    name: str
    provider: Provider = Provider.openai
    model: str
    system_prompt: str = ""
    description: str = ""
    provider_credential_id: UUID | None = None
    fallback_credential_id: UUID | None = None
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode = SessionMode.stateful
    settings: dict[str, Any] = {}


class UpdateAgentRequest(BaseModel):
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


class AgentResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    provider: Provider
    model: str
    provider_credential_id: UUID | None = None
    fallback_credential_id: UUID | None = None
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode | None = None
    system_prompt: str = ""
    description: str = ""
    status: AgentStatus
    settings: dict[str, Any] = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None
