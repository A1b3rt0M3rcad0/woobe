from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

import uuid6

from modules.ai.domain.enums import (
    AgentStatus,
    AgentType,
    CredentialStatus,
    Provider,
    SessionMode,
)


@dataclass
class ProviderCredential:
    id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    provider: Provider = Provider.openai
    name: str = ""
    encrypted_secret: str = ""
    status: CredentialStatus = CredentialStatus.active
    last_validated_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Agent:
    id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    provider_credential_id: UUID | None = None
    fallback_credential_id: UUID | None = None
    name: str = ""
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
    status: AgentStatus = AgentStatus.active
    settings: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
