from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CreateProviderCredentialRequest(BaseModel):
    project_id: UUID
    provider: str
    name: str
    secret: str


class ProviderCredentialResponse(BaseModel):
    id: UUID
    project_id: UUID
    provider: str
    name: str
    status: str
    created_at: datetime


class CreateAgentRequest(BaseModel):
    project_id: UUID
    name: str
    provider: str = "openai"
    model: str
    system_prompt: str = ""
    description: str = ""
    temperature: float | None = None
    max_output_tokens: int | None = None
    settings: dict[str, Any] = {}


class AgentResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    provider: str
    model: str
    status: str
    created_at: datetime
