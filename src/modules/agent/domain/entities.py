from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

import uuid6

from modules.agent.domain.enums import (
    AgentStatus,
    AgentType,
    ContractStatus,
    CredentialStatus,
    ModelConfigStatus,
    PromptStatus,
    Provider,
    ReleaseStatus,
    ReleaseTestStatus,
    SessionMode,
    ValidationMode,
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
    metadata: dict[str, Any] = field(default_factory=dict)
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


@dataclass
class AgentPrompt:
    id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    agent_id: UUID = field(default_factory=uuid6.uuid7)
    version: str = ""
    name: str = ""
    content: str = ""
    content_hash: str | None = None
    status: PromptStatus = PromptStatus.draft
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class AgentContract:
    id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    agent_id: UUID = field(default_factory=uuid6.uuid7)
    version: str = ""
    name: str = ""
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    validation_mode: ValidationMode = ValidationMode.loose
    repair_attempts: int = 0
    additional_instructions: str | None = None
    schema_hash: str | None = None
    status: ContractStatus = ContractStatus.draft
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class AgentModelConfig:
    id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    agent_id: UUID = field(default_factory=uuid6.uuid7)
    version: str = ""
    provider: Provider = Provider.openai
    provider_credential_id: UUID | None = None
    model: str = ""
    base_url: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode | None = None
    settings: dict[str, Any] = field(default_factory=dict)
    status: ModelConfigStatus = ModelConfigStatus.draft
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class AgentRelease:
    id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    agent_id: UUID = field(default_factory=uuid6.uuid7)
    version: str = ""
    status: ReleaseStatus = ReleaseStatus.draft
    prompt_version_id: UUID | None = None
    contract_version_id: UUID | None = None
    knowledge_version_id: UUID | None = None
    model_config_version_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    response_format: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    provider: str | None = None
    model: str | None = None
    provider_credential_id: UUID | None = None
    fallback_provider: str | None = None
    fallback_model: str | None = None
    fallback_credential_id: UUID | None = None
    base_url: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: str | None = None
    agent_status: str | None = None
    collection_ids: list[UUID] | None = None
    runtime_config: dict[str, Any] | None = None
    release_notes: str | None = None
    risk_score: int | None = None
    created_by: UUID | None = None
    promoted_by: UUID | None = None
    promoted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class AgentReleaseTest:
    id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    agent_id: UUID = field(default_factory=uuid6.uuid7)
    release_id: UUID | None = None
    contract_version_id: UUID | None = None
    input_payload: dict[str, Any] | None = None
    expected_output: dict[str, Any] | None = None
    actual_output: dict[str, Any] | None = None
    status: ReleaseTestStatus = ReleaseTestStatus.pending
    validation_errors: list[dict[str, Any]] | None = None
    latency_ms: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
