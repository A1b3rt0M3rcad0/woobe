from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import uuid6

from modules.agent.domain.enums import (
    AgentStatus,
    AgentType,
    CollectionStatus,
    ContractStatus,
    CredentialStatus,
    DocumentStatus,
    KnowledgeVersionStatus,
    MessageRole,
    ModelConfigStatus,
    ParserType,
    PromptStatus,
    Provider,
    ProviderModelStatus,
    ReleaseStatus,
    ReleaseTestStatus,
    RiskLevel,
    RuntimeSessionMode,
    SecretType,
    SessionMode,
    SessionStatus,
    ToolStatus,
    ToolType,
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
class ProviderModel:
    id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    provider_credential_id: UUID = field(default_factory=uuid6.uuid7)
    name: str = ""
    model: str = ""
    model_type: str | None = None
    spec: dict[str, Any] | None = None
    spec_version: int | None = None
    spec_hash: str | None = None
    status: ProviderModelStatus = ProviderModelStatus.active
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Agent:
    id: UUID = field(default_factory=uuid6.uuid7)
    project_id: UUID = field(default_factory=uuid6.uuid7)
    provider_model_id: UUID | None = None
    fallback_provider_model_id: UUID | None = None
    provider_credential_id: UUID | None = None
    fallback_credential_id: UUID | None = None
    name: str = ""
    description: str = ""
    type: AgentType = AgentType.chat
    behavior_spec: dict[str, Any] | None = None
    system_prompt: str = ""
    provider: Provider = Provider.openai
    model: str = ""
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode = SessionMode.stateful
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
    provider_model_id: UUID | None = None
    fallback_provider_model_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    behavior_spec: dict[str, Any] | None = None
    system_prompt: str | None = None
    response_format: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    external_context_contract: dict[str, Any] | None = None
    provider: str | None = None
    model: str | None = None
    provider_credential_id: UUID | None = None
    model_spec_snapshot: dict[str, Any] | None = None
    model_spec_hash: str | None = None
    fallback_model_spec_snapshot: dict[str, Any] | None = None
    fallback_model_spec_hash: str | None = None
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


@dataclass
class DocumentCollection:
    project_id: UUID | None = None
    name: str = ""
    description: str | None = None
    status: CollectionStatus = CollectionStatus.ACTIVE
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class AgentCollection:
    agent_id: UUID
    collection_id: UUID
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Document:
    project_id: UUID | None = None
    collection_id: UUID | None = None
    title: str = ""
    file_name: str = ""
    content_type: str = ""
    size_bytes: int = 0
    storage_key: str = ""
    parser: ParserType = ParserType.TEXT
    status: DocumentStatus = DocumentStatus.UPLOADED
    error: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    sha256: str | None = None
    indexed_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class DocumentChunk:
    project_id: UUID | None = None
    collection_id: UUID | None = None
    document_id: UUID | None = None
    content: str = ""
    chunk_index: int = 0
    token_count: int | None = None
    page_number: int | None = None
    section_title: str | None = None
    data: dict | None = None
    embedding: list[float] | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class KnowledgeVersion:
    project_id: UUID | None = None
    agent_id: UUID | None = None
    version: str = ""
    collection_ids: list[UUID] = field(default_factory=list)
    document_ids: list[UUID] | None = None
    snapshot_metadata: dict | None = None
    status: KnowledgeVersionStatus = KnowledgeVersionStatus.DRAFT
    id: UUID = field(default_factory=uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Tool:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID | None = None
    agent_id: UUID | None = None
    name: str = ""
    description: str | None = None
    type: ToolType = ToolType.FUNCTION
    config: dict | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    timeout_ms: int | None = None
    status: ToolStatus = ToolStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Secret:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID | None = None
    name: str = ""
    type: SecretType = SecretType.CUSTOM
    encrypted_value: str = ""
    data: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Session:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID | None = None
    agent_id: UUID | None = None
    runtime_environment: str = "draft"
    opened_release_id: UUID | None = None
    external_session_id: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    status: SessionStatus = SessionStatus.ACTIVE
    mode: RuntimeSessionMode = RuntimeSessionMode.CHAT
    data: dict | None = None
    external_context_snapshot: dict[str, Any] | None = None
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


@dataclass
class AskJob:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID | None = None
    agent_id: UUID | None = None
    session_id: UUID | None = None
    status: str = "pending"
    params: dict | None = None
    result: dict | None = None
    error: str | None = None
    trace_id: UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
