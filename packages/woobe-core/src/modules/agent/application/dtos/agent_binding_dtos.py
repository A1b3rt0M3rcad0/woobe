from typing import Any
from uuid import UUID

from pydantic import BaseModel

from modules.agent.domain.enums import AgentStatus, AgentType, Provider, SessionMode


class CreateAgentInput(BaseModel):
    project_id: UUID
    provider_model_id: UUID | None = None
    fallback_provider_model_id: UUID | None = None
    provider_credential_id: UUID | None = None
    fallback_credential_id: UUID | None = None
    name: str
    description: str = ""
    type: AgentType = AgentType.chat
    system_prompt: str = ""
    provider: Provider = Provider.openai
    model: str = ""
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode = SessionMode.stateless
    settings: dict[str, Any] = {}


class UpdateAgentInput(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    provider: Provider | None = None
    model: str | None = None
    provider_model_id: UUID | None = None
    fallback_provider_model_id: UUID | None = None
    provider_credential_id: UUID | None = None
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    fallback_credential_id: UUID | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode | None = None
    status: AgentStatus | None = None
    settings: dict[str, Any] | None = None
